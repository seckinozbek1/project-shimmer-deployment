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
             units are read on the kept text, and an index into a part cut mid-text is
             not evidence; a build without a budget, or with a document off its declared
             side, is refused, and a development build that declares no side refuses a
             holdout document; ContractNLI reads only the frozen file of its side; an
             empty document is skipped; one word rule (section 5.6, Words) counts every
             part, band and cut line; ContractNLI makes one part per span of the
             agreement's own span list, or merged parts under the cost fallback; the
             bands command gives every document's words, band and side with no build,
             and band totals for the holdout pool alone and the development side apart,
             a FinDVer test filing testmini also holds removed (a mixed-side input),
             ContraDoc's sides read from the frozen assignment alone (refused without
             it, as a holdout build is); listed demonstration documents are excluded
  cli        the command line in a fresh `-I` interpreter from a copied tree (no
             repository on the path): a FinDVer build with every budget option, its own
             --reports option wired through, a table that already has a separator row
             kept as it is, the token counter's SHA-256 recorded, an option the adapter
             does not take refused; SciTab with --exclude and CUAD holdout builds; a
             ContractNLI holdout build with --frozen-sha256 and --parts merged (a wrong
             hash and a development build of a non-frozen file refused); bands and split
  development  counts only, on the B-dev development items when external/ holds them
             (skipped otherwise): every adapter builds its development file; the counts
             the preregistration lists in section 5.7 hold (ContractNLI parts, spans,
             splitter and short evidence parts; ContraDoc grouping, one-part documents
             and evidence sentences; FinDVer table entries, CIKs and development bands)
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
             against another relation, prior relations, a settled answer on one unit
             against a refusal on another, figure-audit records in one-rule and
             several-rule bundles), for B2, B1 and B0, with S-1, S-2, S-3 and S-5; a
             figure-audit record is a figure-audit relation stamped python on every
             benchmark (band records decide their rule's item, a model-written record
             always decides, a computed blank-cell record on a CUAD-shaped bundle does
             not); S-5 puts a refusal before an ok record, and a failed run decides no
             item by ok over refusal; B3 and B4 are read from the bus (decision
             DS5-8, adopted by D-056), so a run with no bus is a run failure, and
             with the flag off they are refused; the catch layer is read from the
             WRITTEN-BY-A stamp alone, compared exactly
  records    one record reader (common/records.py): B2 from review_data.json, B3 from
             the run's bus, written_by stamped from the line, supersession within
             (agent, document, item_id), a judged absence counted only by Python's
             stamped copy with the raw copy listed apart; every mapping fixture moved
             onto a bus gives the same labels as its review_data.json form, and the
             label command labels B3 and B4 from a fixture bus (BUS_READER_ADOPTED)
  incomplete D-066 and D-068: a run that reached its end with exit code 0 and
             semantic_complete false is not a run failure and is labelled from its
             records (a stopped run that did not reach its end still is one); S-6
             makes every item of such a document ABSTAIN; an item no record decides
             whose rule's judging calls all failed is ABSTAIN item_calls_failed through
             the run's own registry id map (adopted, D-078; a missing, unreadable or
             many-to-one map is not used, the row says why, the document is counted;
             with the switch off the row says whether it would have applied); a
             pairing-map refusal naming a registry id refuses its operator id's item;
             completeness per document (the
             PROCESSOR calls accepted against made, a partial delivery, the pairs made
             from it, the items a record of it decided); the items a band record
             flagged (section 12 item 3); a D-068 kept answer on the
             bus decides its rule's item as a model's record. Each by neutralise,
             fail, restore, pass
  overcontext  section 5.3 and open point 12.14 (D-078): a B3 document whose run has a
             reply record with context.over_context true is excluded (basis
             over_context_excluded, listed and counted), left out of every scored
             analysis but S-7, which scores its items ABSTAIN, and out of the paired
             view (score --paired-with) for both arms; reply records that fit change no
             label; B4 is not checked; the saved L4b FinDVer run reads 3 such calls where
             external/ holds it (skipped otherwise). Each by neutralise, fail, restore, pass
  s8         sensitivity S-8 (DEV-012): B3 and B4 as if every record a model wrote were
             absent (only `written_by` exactly `python` kept, an unstamped record a
             model's): an item a model's record decided takes the next line of section
             5.1 (a Python ok, a Python refusal), else silence; a Python-decided item, a
             run failure and an over-context exclusion unchanged; B0, B1 and B2 equal
             their primary in labels and score and say so. Neutralise, fail, restore, pass
  setupfailure  one setup-failure rule for B1 and B3 (D-084, DEV-014): a B1 document whose
             output holds b1_setup_failure.json and a B3 document with a call that failed
             out of memory are ABSTAIN with basis setup_failure on every item, counted
             apart, left out of that arm's scoring in every analysis but S-7 (ABSTAIN
             there) and out of the paired view; any other failed call is no setup
             failure. Each by neutralise, fail, restore, pass
  synthetic  B's synthetic tests (benchmark/adapters/synthetic, preregistration section
             13), on a hand-written test of three bundles: items from the targets file
             and the conventions, never the key; Shimmer's unit ids (on every development
             suite document too, where generated); B0, B1, B2 and B3 labels and scores by
             hand (location by unit and relation under any rule, the attribution apart,
             the reason by the key's claim, false positives, distractor hits, the twin's
             false alarms, S-8; a negotiation-style key left unscored); the B1 prompt for
             a synthetic item. Each by neutralise, fail, restore, pass
  dryrun     benchmark/dryrun: the content-blind dry-run choice (words, band, side and
             opaque id only; sorted by words then id; evenly spaced positions; each
             replacement listed), the build restricted to chosen documents, B2 on it,
             the B1 prompt tokens and the memory bound computed by hand (D-056
             condition 8: float32 non-4-bit weights, activations and KV cache; sdpa
             with no T x T term; the eager reference squared over the prompt only),
             and its recomputation from a written summary
  metrics    each benchmark's metric on a tiny confusion example equals the hand
             computation written beside it, with its headline named; an end-to-end
             score on a built bundle gives the hand-computed accuracy, location recall
             (B1 by containment either way on a benchmark that marks parts, the reverse
             way only for a unit of at least 5 words) and false positives, and S-4
             leaves out the items whose evidence lies beyond the cut
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "benchmark" / "adapters"
# The B-dev development items (third-party, gitignored, never copied into tracked files);
# `py -3.12 -X utf8 scripts/adapter_checks.py --external <folder>` points elsewhere.
EXTERNAL = ROOT / "external"
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
                                            "prompt", "records", "segments")}
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
    """A build of the synthetic items; --development unless the caller says otherwise.
    The fixtures mix sides on purpose, so a development build of them is `synthetic`
    (cli.build's keyword for the checks alone) unless the caller says otherwise."""
    options.setdefault("development", True)
    options.setdefault("synthetic", bool(options["development"]))
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
        self.assertEqual(record["items_evidence_beyond_cut"], [answer["item_id"]])
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

    def test_an_index_into_a_part_cut_mid_text_is_not_evidence(self):
        # D-039 item 8: evidence marked by index (FinDVer's context indices, ContractNLI's
        # spans) is evidence only in a part kept whole. One filing of one 20-word paragraph,
        # one refuted claim citing it; budget 162 - 100 - 10 - 32 = 20: the title (2), the
        # heading (2) and the label line (2) leave 3 words beside the 11-word cut line, so
        # the part is cut mid-text. Its index then marks no unit, and the item is listed
        # in parts.json as having its evidence beyond the cut (S-4 leaves it out).
        data, reports = self.root / "fv" / "data", self.root / "fv" / "financial_reports"
        data.mkdir(parents=True)
        reports.mkdir()
        (reports / "ZQX-2024-03-31_10-Q.json").write_text(json.dumps({
            "url": "https://filings.example.invalid/Archives/edgar/data/9990000003/x/zqx-10q.htm",
            "context": [{"id": 0, "type": "paragraph",
                         "context": " ".join("w%d" % i for i in range(1, 21))}]}), encoding="utf-8")
        (data / "testmini.json").write_text(json.dumps([{
            "example_id": "syn-cut-1", "subset": "ie", "split": "testmini", "statement": "w9 is there.",
            "entailment_label": False, "relevant_context": [0],
            "report": "ZQX-2024-03-31_10-Q.json"}]), encoding="utf-8")
        _build("findver", self.root / "b", data / "testmini.json", reports=reports,
               max_context=162, output_allowance=10, token_counter=WordCounter(100))
        record = _json(self.root / "b" / "parts.json")["documents"][0]
        self.assertEqual((record["cut"]["cut"], record["cut"]["whole_parts_kept"]), (True, 0))
        answer = _json(self.root / "b" / record["document_id"] / "answer_key.json")["items"][0]
        self.assertEqual((answer["evidence_unit_ids"], answer["evidence_beyond_cut"]), ([], True))
        self.assertEqual(record["items_evidence_beyond_cut"], [answer["item_id"]])
        # The same filing uncut: the index marks its part.
        _build("findver", self.root / "u", data / "testmini.json", reports=reports)
        record = _json(self.root / "u" / "parts.json")["documents"][0]
        answer = _json(self.root / "u" / record["document_id"] / "answer_key.json")["items"][0]
        self.assertEqual((answer["evidence_unit_ids"], answer["evidence_beyond_cut"],
                          record["items_evidence_beyond_cut"]), (["u01-p-00001"], False, []))

    def test_one_word_rule_for_bands_and_the_cut_line(self):
        # Section 5.6, Words (D-039 item 12): Python's str.split() with no argument, line by
        # line; on a pipe row (table text) a token made only of `-`, `:` and `|` is not a
        # word, on any other line every token is. A table cell (SciTab) is table text. One
        # function counts every part, the band and the cut line.
        c = _common()
        prose = "Revenue | 2023 rose :--| 5 percent -- a|b ||"
        self.assertEqual(c["ids"].word_count(prose), 10)
        row = "| A | --- | :-: | b-c | ||"
        self.assertEqual(c["ids"].word_count(row), 2)
        self.assertEqual(c["ids"].word_count(prose + "\n" + row + "\n| x |\n|---|---|"), 13)
        self.assertEqual(c["cut"].words(prose), c["ids"].word_count(prose))
        self.assertEqual([c["ids"].cell_word_count(v) for v in ("-", "n/a", "--", "71.2 x", "")],
                         [0, 1, 0, 2, 0])
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
        entry = _json(_fixture("findver", "financial_reports/ZQX-2024-01-31_10-K.json"))["context"][1]
        self.assertEqual((_adapter("findver").entry_text(entry)[2], len(entry["context"].split())), (17, 26))
        # A table that already has a separator row (`| :--- | ---: |`): its tokens are markup.
        entry = _json(_fixture("findver", "financial_reports/ZQY-WT-2024-02-29_10-Q.json"))["context"][3]
        self.assertEqual(_adapter("findver").entry_text(entry)[2], 7)

    def test_budget_is_computed_per_document_from_its_own_conventions(self):
        # One line per convention in the B1 prompt: the two-claim table's prompt is one
        # line longer than the one-claim table's, so its budget is one token smaller.
        _build("scitab", self.root / "b", max_context=5000, output_allowance=100,
               token_counter=WordCounter(lines=True))
        docs = {d["source_document_id"]: d["cut"] for d in _json(self.root / "b" / "parts.json")["documents"]}
        self.assertEqual(docs["syn-tab-1"]["prompt_overhead"] - docs["syn-tab-3"]["prompt_overhead"], 1)
        for cut in docs.values():
            self.assertEqual(cut["budget"], 5000 - cut["prompt_overhead"] - 100 - 32)

    def test_development_build_refuses_holdout_documents(self):
        # D-039 item 14: a --development build that declares no side refuses a document on
        # the holdout side (the fixture's syn-paper-a is holdout by the hash rule), unless
        # --side holdout is also given; the fixture's development paper alone builds.
        records = _json(_fixture("scitab", "synthetic_items.json"))
        held = [r for r in records if r["paper_id"] == "syn-paper-a"]
        dev = [r for r in records if r["paper_id"] == "syn-paper-bz"]
        self.assertTrue(held and dev)
        mixed, holdout, development = (self.root / n for n in ("mixed.json", "held.json", "dev.json"))
        mixed.write_text(json.dumps(records), encoding="utf-8")
        holdout.write_text(json.dumps(held), encoding="utf-8")
        development.write_text(json.dumps(dev), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "refuses holdout documents unless --side holdout"):
            _build("scitab", self.root / "a", mixed, synthetic=False)
        self.assertFalse((self.root / "a").exists() and any((self.root / "a").iterdir()))
        with self.assertRaisesRegex(ValueError, "refuses holdout documents"):
            _build("scitab", self.root / "b", holdout, synthetic=False)
        _build("scitab", self.root / "c", holdout, synthetic=False, side="holdout")
        self.assertEqual({d["side"] for d in _json(self.root / "c" / "parts.json")["documents"]}, {"holdout"})
        _build("scitab", self.root / "d", development, synthetic=False)
        self.assertNotIn("synthetic_fixture_build", _json(self.root / "d" / "parts.json"))
        _build("scitab", self.root / "e", mixed)
        self.assertTrue(_json(self.root / "e" / "parts.json")["synthetic_fixture_build"])
        # FinDVer's items carry their official split: with no side declared, a filing whose
        # items are all of `test` is a holdout document, and is refused.
        test_items = [dict(r, split="test") for r in _json(_source("findver"))]
        source = self.root / "fv" / "data" / "test.json"
        source.parent.mkdir(parents=True)
        source.write_text(json.dumps(test_items), encoding="utf-8")
        reports = _fixture("findver", "financial_reports")
        with self.assertRaisesRegex(ValueError, "refuses holdout documents"):
            _build("findver", self.root / "f", source, reports=reports, synthetic=False)
        _build("findver", self.root / "g", _source("findver"), reports=reports, synthetic=False)
        self.assertEqual({d["side"] for d in _json(self.root / "g" / "parts.json")["documents"]},
                         {"development"})

    def test_contractnli_reads_only_the_frozen_file_of_its_side(self):
        # D-039 item 14: the development side is dev.json by the SHA-256 the B-dev manifest
        # records; the holdout side is the file whose SHA-256 role B passes; train.json, or
        # any other file, is refused for either side, and so is a development build of it.
        adapter = _adapter("contractnli")
        fixture = _fixture("contractnli", "synthetic_items.json")
        digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
        budget = dict(max_context=5000, output_allowance=10, token_counter=WordCounter())
        with self.assertRaisesRegex(ValueError, "not the frozen ContractNLI file for the development side"):
            _build("contractnli", self.root / "a", development=False, side="development", **budget)
        with self.assertRaisesRegex(ValueError, "not the frozen ContractNLI file for the development side"):
            _build("contractnli", self.root / "b", synthetic=False)
        with self.assertRaisesRegex(ValueError, "needs --frozen-sha256"):
            _build("contractnli", self.root / "c", development=False, side="holdout", **budget)
        with self.assertRaisesRegex(ValueError, "not the frozen ContractNLI file for the holdout side"):
            _build("contractnli", self.root / "d", development=False, side="holdout",
                   frozen_sha256="0" * 64, **budget)
        with self.assertRaisesRegex(ValueError, "names the development file"):
            _build("contractnli", self.root / "e", development=False, side="holdout",
                   frozen_sha256=adapter.FROZEN_DEV_SHA256, **budget)
        _build("contractnli", self.root / "f", development=False, side="holdout",
               frozen_sha256=digest, **budget)
        self.assertEqual(_json(self.root / "f" / "parts.json")["input_check"],
                         {"input_sha256": digest, "frozen_for": "holdout"})
        with mock.patch.object(adapter, "FROZEN_DEV_SHA256", digest):
            _build("contractnli", self.root / "g", development=False, side="development", **budget)
            _build("contractnli", self.root / "h", synthetic=False)
        self.assertEqual(_json(self.root / "h" / "parts.json")["input_check"]["frozen_for"], "development")

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
        doc = ids_.opaque_document_id("findver", "ZQX-2024-01-31_10-K.json")
        record = next(d for d in _json(self.root / "b" / "parts.json")["documents"] if d["document_id"] == doc)
        # 5 words; 6 + 6 cell words + 5 (pipes not counted); `#` is a word, 2 + 5.
        self.assertEqual([p["words"] for p in record["parts"]], [5, 17, 7])
        self.assertEqual([p["source"] for p in record["parts"]],
                         [{"context_index": 0, "kind": "paragraph"}, {"context_index": 1, "kind": "table"},
                          {"context_index": 2, "kind": "paragraph"}])
        # an impossible CIK on a reserved host: no real filer is named by a fixture
        self.assertEqual((record["issuer_cik"], record["context_index_base"]), (9990000001, 0))
        self.assertEqual(record["report_sha256"], hashlib.sha256(
            _fixture("findver", "financial_reports/ZQX-2024-01-31_10-K.json").read_bytes()).hexdigest())
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
        # A table entry that already has a separator row after its first row keeps it, and
        # gets no second one.
        other = ids_.opaque_document_id("findver", "ZQY-WT-2024-02-29_10-Q.json")
        text = (self.root / "b" / other / "context" / (other + ".md")).read_text(encoding="utf-8")
        self.assertIn("Staff by region:\n| Region | Staff |\n| :--- | ---: |\n| North | 12 |", text)
        self.assertNotIn("|---|---|", text)
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

    def test_contractnli_merged_parts_under_the_cost_fallback(self):
        # D-039 item 2, section 5.6: under `--parts merged` the pieces (spans and the
        # stretches between them) are joined in order into parts of at least 100 words, the
        # last part possibly shorter, and an evidence index marks the part that holds its
        # span. With a minimum of 12 the fixture's 7101 (pieces of 3, 10, 7, 8, 2 and 10
        # words, spans 0 to 6, span 3 a single space) gives [0, 1] (13), [2, 4] (15) and
        # [5, 6] (12).
        adapter = _adapter("contractnli")
        data = adapter.read_source(_fixture("contractnli", "synthetic_items.json"))
        record = next(d for d in data["documents"] if d["id"] == 7101)
        pieces = adapter.span_pieces(record["text"], record["spans"])
        merged = adapter.merged_pieces(record["text"], pieces, minimum=12)
        self.assertEqual([m["spans"] for m in merged], [[0, 1], [2, 4], [5, 6]])
        self.assertEqual(merged[0]["start"], pieces[0]["start"])
        self.assertEqual(merged[-1]["end"], pieces[-1]["end"])
        # At the preregistered 100 words each fixture agreement (under 100 words) is one
        # part, which holds every span, so every evidence index marks it.
        _build("contractnli", self.root / "m", parts="merged")
        doc = _common()["ids"].opaque_document_id("contractnli", 7101)
        parts = next(d for d in _json(self.root / "m" / "parts.json")["documents"] if d["document_id"] == doc)
        self.assertEqual((parts["part_rule"], len(parts["parts"])), ("merged", 1))
        self.assertEqual(parts["parts"][0]["source"]["spans"], [0, 1, 2, 4, 5, 6])
        answers = {a["hypothesis_key"]: a for a in _json(self.root / "m" / doc / "answer_key.json")["items"]}
        self.assertEqual(answers["nda-2"]["evidence_unit_ids"], ["u01-p-00001"])
        with self.assertRaisesRegex(ValueError, "--parts is span or merged"):
            _build("contractnli", self.root / "x", parts="sentences")

    def test_bands_command_without_a_build(self):
        # D-039 item 7: `bands` gives every document's words and band by the one word rule,
        # over a whole input, with no build: the same figures a build records in parts.json,
        # and per band the documents, items and median words.
        # Each document also carries the side a build records, and the band totals are the
        # holdout pool's alone, the development side's apart (S4 round 3, decision C).
        c = _common()
        contractnli = _adapter("contractnli")
        assignment = self.root / "contradoc_split.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(c["cli"].main(_adapter("contradoc"), [
                "split", "--input", str(_source("contradoc")), "--out", str(assignment)]), 0)
        for name in NAMES:
            options = {"reports": _fixture("findver", "financial_reports")} if name == "findver" else {}
            if name == "contradoc":
                options = {"assignment": assignment}
            with mock.patch.object(contractnli, "FROZEN_DEV_SHA256",
                                   hashlib.sha256(_source("contractnli").read_bytes()).hexdigest()):
                result = c["cli"].bands(_adapter(name), _source(name), **options)
            _build(name, self.root / name)
            built = {d["document_id"]: d for d in _json(self.root / name / "parts.json")["documents"]}
            if name == "contractnli":
                # the synthetic build lifts the frozen-file check; bands never does, so its
                # side is the patched frozen file's (development)
                built = {k: dict(d, side="development") for k, d in built.items()}
            self.assertEqual({r["document_id"]: (r["words"], r["length_band"], r["side"])
                              for r in result["documents"]},
                             {k: (d["source_words"], d["length_band"], d["side"]) for k, d in built.items()}, name)
            items = _json(self.root / name / "items.json")["items"]
            for key, side in (("holdout_pool_bands", "holdout"), ("development_bands", "development")):
                mine = {k for k, d in built.items() if d["side"] == side}
                self.assertEqual(sum(b["documents"] for b in result[key].values()), len(mine), name + key)
                self.assertEqual(sum(b["items"] for b in result[key].values()),
                                 sum(1 for i in items if i["document_id"] in mine), name + key)
            self.assertEqual(result["input_sha256"], hashlib.sha256(_source(name).read_bytes()).hexdigest())
        result = c["cli"].bands(_adapter("contradoc"), _source("contradoc"), assignment=assignment)
        self.assertEqual(result["documents_by_side"], {"development": 1, "holdout": 3})
        words = sorted(r["words"] for r in result["documents"]
                       if r["length_band"] == "A" and r["side"] == "holdout")
        self.assertEqual(result["holdout_pool_bands"]["A"]["median_words"], words[1])
        # ContractNLI's side is its frozen file's, checked as a build checks it
        with self.assertRaisesRegex(ValueError, "not the frozen ContractNLI file"):
            c["cli"].bands(contractnli, _source("contractnli"))
        digest = hashlib.sha256(_source("contractnli").read_bytes()).hexdigest()
        result = c["cli"].bands(contractnli, _source("contractnli"), frozen_sha256=digest)
        self.assertEqual(result["documents_by_side"], {"holdout": 2})
        with self.assertRaisesRegex(ValueError, "options this adapter does not take: testmini"):
            c["cli"].bands(_adapter("scitab"), _source("scitab"), testmini=_source("findver"))

    def test_contradoc_bands_need_the_frozen_assignment(self):
        # S4 tie-break item a (section 1 and 5.6): `bands` records each ContraDoc document's
        # side as a build records it, from the frozen --assignment, and a ContraDoc input
        # without it is refused, as a holdout build refuses it; the input is never regrouped.
        # A sample holding only 102 keeps 102 in group 101 (its near-duplicate 101 is not
        # in the sample), where regrouping the sample would make 102 its own group.
        c = _common()
        adapter = _adapter("contradoc")
        records = _json(_source("contradoc"))
        assignment = self.root / "assignment.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(c["cli"].main(adapter, ["split", "--input", str(_source("contradoc")),
                                                     "--out", str(assignment)]), 0)
        sample = self.root / "sample.json"
        sample.write_text(json.dumps({"neg": {"102": records["neg"]["102"]}}), encoding="utf-8")
        budget = dict(max_context=5000, output_allowance=10, token_counter=WordCounter())
        for source in (_source("contradoc"), sample):
            with self.assertRaisesRegex(ValueError, "needs --assignment"):
                _build("contradoc", self.root / "h", source, development=False, side="holdout", **budget)
            with self.assertRaisesRegex(ValueError, "needs --assignment"):
                c["cli"].bands(adapter, source)
        result = c["cli"].bands(adapter, sample, assignment=assignment)
        _build("contradoc", self.root / "b", sample, development=False, side="holdout",
               assignment=assignment, **budget)
        built = _json(self.root / "b" / "parts.json")["documents"]
        self.assertEqual([(r["document_id"], r["side"]) for r in result["documents"]],
                         [(d["document_id"], d["side"]) for d in built])
        self.assertEqual(result["assignment_sha256"], hashlib.sha256(assignment.read_bytes()).hexdigest())
        # through the command line: refused with exit code 4 and nothing written
        out = self.root / "bands.json"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = c["cli"].main(adapter, ["bands", "--input", str(sample), "--out", str(out)])
        self.assertEqual((code, out.exists()), (4, False), err.getvalue())
        self.assertIn("needs --assignment", err.getvalue())

    def test_bands_on_a_mixed_side_findver_input(self):
        # Decision C: one input holding a development filing, a holdout filing and a holdout
        # filing that testmini also holds. The band totals count the holdout pool alone (the
        # overlap removed, as section 1 removes it) and the development side apart; without
        # --testmini a holdout input is refused.
        c = _common()
        records = _json(_source("findver"))
        reports = self.root / "financial_reports"
        shutil.copytree(_fixture("findver", "financial_reports"), reports)
        shutil.copy2(reports / "ZQX-2024-01-31_10-K.json", reports / "ZQW-2024-03-31_10-Q.json")
        dev = [r for r in records if r["report"] == "ZQX-2024-01-31_10-K.json"]
        pool = [dict(r, split="test") for r in records if r["report"] == "ZQY-WT-2024-02-29_10-Q.json"]
        overlap = [dict(r, example_id=r["example_id"] + "-w", report="ZQW-2024-03-31_10-Q.json", split="test")
                   for r in dev[:2]]
        data = self.root / "data"
        data.mkdir()
        mixed, mini = data / "mixed.json", data / "mini.json"
        mixed.write_text(json.dumps(dev + pool + overlap), encoding="utf-8")
        mini.write_text(json.dumps(dev + [dict(r, split="testmini") for r in overlap]), encoding="utf-8")
        result = c["cli"].bands(_adapter("findver"), mixed, testmini=mini, reports=reports)
        sides = {r["source_document_id"]: (r["side"], r["items"]) for r in result["documents"]}
        self.assertEqual(sides, {"ZQX-2024-01-31_10-K.json": ("development", len(dev)),
                                 "ZQY-WT-2024-02-29_10-Q.json": ("holdout", len(pool)),
                                 "ZQW-2024-03-31_10-Q.json": ("removed_overlap", len(overlap))})
        self.assertEqual(result["documents_by_side"], {"development": 1, "holdout": 1, "removed_overlap": 1})
        totals = lambda key: (sum(b["documents"] for b in result[key].values()),
                              sum(b["items"] for b in result[key].values()))
        self.assertEqual(totals("holdout_pool_bands"), (1, len(pool)))
        self.assertEqual(totals("development_bands"), (1, len(dev)))
        self.assertEqual(result["testmini_sha256"], hashlib.sha256(mini.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, "needs --testmini"):
            c["cli"].bands(_adapter("findver"), mixed, reports=reports)
        # the command line takes --testmini and prints the two totals
        out = self.root / "bands.json"
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            code = c["cli"].main(_adapter("findver"), ["bands", "--input", str(mixed), "--testmini", str(mini),
                                                       "--reports", str(reports), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(printed.getvalue())["holdout_pool_bands"], result["holdout_pool_bands"])
        self.assertEqual(_json(out)["documents_by_side"], result["documents_by_side"])

    def test_demonstration_documents_are_excluded(self):
        # D-039 item 15, section 1: the documents a benchmark's own paper prints as
        # in-context examples, as role B identified them, are removed with all their items
        # from a build, from `bands`, and marked in `split`.
        c = _common()
        listed = self.root / "exclude.json"
        listed.write_text(json.dumps({"source_document_ids": ["syn-tab-1"]}), encoding="utf-8")
        _build("scitab", self.root / "b", exclude=listed)
        record = _json(self.root / "b" / "parts.json")
        self.assertNotIn("syn-tab-1", {d["source_document_id"] for d in record["documents"]})
        self.assertEqual([(r["source_document_id"], r["items"]) for r in record["excluded_documents"]],
                         [("syn-tab-1", 2)])
        self.assertEqual(record["exclusion_sha256"], hashlib.sha256(listed.read_bytes()).hexdigest())
        self.assertNotIn("syn-tab-1", {r["source_document_id"] for r in
                                       c["cli"].bands(_adapter("scitab"), _source("scitab"), exclude=listed)["documents"]})
        out = self.root / "split.json"
        with contextlib.redirect_stdout(io.StringIO()):
            code = c["cli"].main(_adapter("scitab"), ["split", "--input", str(_source("scitab")),
                                                      "--exclude", str(listed), "--out", str(out)])
        self.assertEqual(code, 0)
        sides = {r["source_document_id"]: r["side"] for r in _json(out)["documents"]}
        self.assertEqual(sides["syn-tab-1"], "excluded_demonstration")

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
        fixture = _fixture("contractnli", "synthetic_items.json")
        data = adapter.read_source(fixture)
        digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
        for side in ("development", "holdout"):
            args = type("A", (), {"official": side})()
            self.assertEqual({r["side"] for r in adapter.split_rows(data, args)}, {side})
            budget = dict(max_context=5000, output_allowance=10, token_counter=WordCounter())
            frozen = digest if side == "development" else adapter.FROZEN_DEV_SHA256
            with mock.patch.object(adapter, "FROZEN_DEV_SHA256", frozen):
                _build("contractnli", self.root / side, development=False, side=side,
                       frozen_sha256=digest if side == "holdout" else None, **budget)
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
        self.assertEqual(rows, {"ZQX-2024-01-31_10-K.json": "removed_overlap",
                                "ZQY-WT-2024-02-29_10-Q.json": "holdout"})


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
                # B3 and B4 are read from the bus (D-056): these runs carry review_data.json
                # only, so each is a run failure (no bus) and every item ABSTAIN, never
                # labelled from review_data.json
                pipeline = c["cli"].label(adapter, items, arm, runs)["primary"]
                self.assertEqual({r["class"] for r in pipeline["labels"]}, {"ABSTAIN"}, name + " " + arm)
                self.assertTrue(all(d["run_failure"] for d in pipeline["documents"]), name + " " + arm)
            for arm, labels in arms.items():
                for variant in ("", " S-1", " S-2", " S-3", " S-5"):
                    key = arm + variant
                    analysis = variant.strip() or "primary"
                    if key in cases["expected"]:
                        self._compare(name, key, labels[analysis], cases["expected"][key])
                    for item_id, detail in cases.get("expected_detail", {}).get(key, {}).items():
                        row = next(r for r in labels[analysis]["labels"] if r["item_id"] == item_id)
                        for field, value in detail.items():
                            self.assertEqual(row[field], value, "%s %s %s %s" % (name, key, item_id, field))
                    for doc, detail in cases.get("expected_documents", {}).get(key, {}).items():
                        row = next(d for d in labels[analysis]["documents"] if d["document_id"] == doc)
                        for field, value in detail.items():
                            got = row["unattached"]["count"] if field == "unattached" else (
                                row["unattached"]["per_deliverable"] if field == "per_deliverable" else row[field])
                            self.assertEqual(got, value, "%s %s %s %s" % (name, key, doc, field))
                for field, value in cases.get("expected_counts", {}).get(arm, {}).items():
                    self.assertEqual(labels["primary"]["counts"][field], value, "%s %s count %s" % (name, arm, field))
            b0 = c["cli"].label(adapter, items, "B0")["primary"]
            self.assertEqual({r["class"] for r in b0["labels"]}, {"CLEAR"}, name + " B0")
        # an adapter fault makes the label command exit 3 (FinDVer: no typed-record key)
        cases = _json(_fixture("findver", "mapping_cases.json"))
        items, runs, _ = _materialise(cases, self.root / "exit")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = c["cli"].main(_adapter("findver"), ["label", "--items", str(items), "--arm", "B2",
                                                       "--runs", str(runs), "--out", str(self.root / "l.json")])
            # B3 is labelled from the bus (D-056); these runs have none, so every item is a
            # run failure (ABSTAIN), not a fault; with the bus reading not adopted it refuses
            bus_arm = c["cli"].main(_adapter("findver"), ["label", "--items", str(items), "--arm", "B3",
                                                          "--runs", str(runs), "--out", str(self.root / "b.json")])
            with mock.patch.object(c["mapping"], "BUS_READER_ADOPTED", False):
                refused = c["cli"].main(_adapter("findver"), ["label", "--items", str(items), "--arm", "B3",
                                                              "--runs", str(runs), "--out", str(self.root / "m.json")])
        self.assertEqual((code, bus_arm, refused), (3, 0, 4))
        self.assertEqual({r["class"] for r in _json(self.root / "b.json")["primary"]["labels"]}, {"ABSTAIN"})
        self.assertFalse((self.root / "m.json").exists(), "a refused arm writes no labels")

    def test_a_settled_answer_on_any_unit_beats_a_refusal(self):
        # D-039 item 1: irregular on any unit, then ok on any unit, then a refusal, then
        # silence, for every benchmark; an ok on one unit and a refusal on another is the
        # benchmark's "holds" label (ContractNLI Entailment, SciTab supports), never its
        # "not settled" one.
        m = _common()["mapping"]

        def record(verdict, unit, **extra):
            return dict({"item_id": "r-" + unit + verdict, "source_rule_id": "CONV-X-1",
                         "unit_id": unit, "relation": "", "record_verdict": verdict}, **extra)
        refusal = record("irregular", "u01", confidence="UNCERTAIN")
        cases = [([refusal, record("ok", "u02")], "CLEAR", "ok"),
                 ([refusal], "UNDECIDED", "refusal"),
                 ([refusal, record("ok", "u02"), record("irregular", "u03")], "FLAG", "irregular"),
                 ([], "CLEAR", "silent")]
        for name in NAMES:
            spec = _adapter(name).SPEC
            for records, cls, basis in cases:
                run = {"failure": False, "records": records, "pairing_refusals": []}
                row = m.classify(spec, "CONV-X-1", run)
                expected = ("CLEAR", "irregular_other_relation") if (name == "cuad" and cls == "FLAG") else (cls, basis)
                self.assertEqual((row["class"], row["basis"]), expected, "%s %s" % (name, basis))
                self.assertEqual(row["refusal_and_ok"], len(records) >= 2, "%s %s" % (name, basis))
        spec = _adapter("contractnli").SPEC
        run = {"failure": False, "records": [refusal, record("ok", "u02")], "pairing_refusals": []}
        self.assertEqual(spec.label(m.classify(spec, "CONV-X-1", run)["class"]), "entailment")

    def test_figure_audit_records_one_definition_for_every_benchmark(self):
        # Section 0 and 5.1 (S4 round 3, lead decision A): a figure-audit record is a record
        # of relation missing_field, below_band, above_band, sum_mismatch or product_mismatch
        # AND stamped `written_by: python`. In a several-rule bundle Python's missing_field,
        # sum_mismatch and product_mismatch records (attributed by shared words) decide no
        # item and are unattached; S-3 attributes them. A band record decides the item of
        # the rule that produced it. A model-written record of any relation decides the item
        # of the rule it was posted for. One rule for all five benchmarks, CUAD included.
        m = _common()["mapping"]
        cuad_rules = ["CONV-CUAD-%02d" % k for k in range(1, 42)]
        for name in NAMES:
            spec = _adapter(name).SPEC
            flag = "FLAG"
            for relation in m.FIGURE_AUDIT_RELATIONS:
                # CUAD's FLAG (absent) is read from missing_field alone (section 5.2)
                want = flag if (name != "cuad" or relation == "missing_field") else "CLEAR"
                python = {"item_id": "rec-p", "source_rule_id": "CONV-A-1", "unit_id": "u02-p-00002",
                          "relation": relation, "record_verdict": "irregular", "written_by": "python"}
                run = {"failure": False, "records": [python], "pairing_refusals": []}
                self.assertTrue(m.is_figure_audit(python))
                self.assertEqual(m.classify(spec, "CONV-A-1", run, rule_count=1)["class"], want,
                                 name + " one rule " + relation)
                row = m.classify(spec, "CONV-A-1", run, rule_count=2)
                if relation in m.BAND_RELATIONS:
                    # a band record decides its producing rule's item, several rules or one
                    self.assertEqual((row["class"], row["figure_audit_set_aside"]), (want, 0),
                                     name + " band " + relation)
                    self.assertEqual(m.unattached(run, ["CONV-A-1", "CONV-A-2"], self.root, "d",
                                                  True)["figure_audit"], 0, name + " " + relation)
                else:
                    self.assertEqual((row["class"], row["basis"], row["figure_audit_set_aside"]),
                                     ("CLEAR", "silent", 1), name + " " + relation)
                    self.assertEqual(m.classify(spec, "CONV-A-1", run, rule_count=2,
                                                attribute_figure_audit=True)["class"], want, name)
                    self.assertEqual(m.unattached(run, ["CONV-A-1", "CONV-A-2"], self.root, "d",
                                                  True)["figure_audit"], 1, name + " " + relation)
                # the same relation written by a model is no figure-audit record: it decides
                for stamp in ({"written_by": "model"}, {}, {"written_by": "Python"}):
                    judged = dict(python, **{"item_id": "rec-j", "absence_path": "judged"})
                    judged.pop("written_by")
                    judged.update(stamp)
                    run = {"failure": False, "records": [judged], "pairing_refusals": []}
                    self.assertFalse(m.is_figure_audit(judged))
                    row = m.classify(spec, "CONV-A-1", run, rule_count=41)
                    self.assertEqual((row["class"], row["figure_audit_set_aside"]), (want, 0),
                                     "%s judged %s %s" % (name, relation, stamp))
        # The CUAD-shaped bundle: 41 rules; a computed blank-cell record on the first rule
        # decides nothing (present) and is unattached; a judged missing_field decides its
        # own rule's item (absent); S-3 attributes the computed one (absent).
        cuad = _adapter("cuad").SPEC
        blank = {"item_id": "rec-b", "source_rule_id": cuad_rules[0], "unit_id": "u01-p-00001",
                 "relation": "missing_field", "record_verdict": "irregular", "written_by": "python",
                 "absence_path": "computed"}
        judged = {"item_id": "rec-j", "source_rule_id": cuad_rules[6], "unit_id": "u03-p-00003",
                  "relation": "missing_field", "record_verdict": "irregular", "written_by": "model",
                  "absence_path": "judged"}
        run = {"failure": False, "records": [blank, judged], "pairing_refusals": []}
        first = m.classify(cuad, cuad_rules[0], run, rule_count=41)
        self.assertEqual((cuad.label(first["class"]), first["basis"], first["figure_audit_set_aside"]),
                         ("present", "silent", 1))
        self.assertEqual(cuad.label(m.classify(cuad, cuad_rules[0], run, rule_count=41,
                                                attribute_figure_audit=True)["class"]), "absent")
        seventh = m.classify(cuad, cuad_rules[6], run, rule_count=41)
        self.assertEqual((cuad.label(seventh["class"]), seventh["layer"]), ("absent", "judged"))
        self.assertEqual(m.unattached(run, cuad_rules, self.root, "d", True)["figure_audit"], 1)
        self.assertFalse(hasattr(cuad, "figure_audit_unattached"), "no per-benchmark exception")

    def test_sensitivity_s5_puts_a_refusal_before_an_ok_record(self):
        # Section 5.1, S-5 (lead decision B): the earlier order, irregular, then a refusal,
        # then ok, then silence, for every pipeline arm on all five benchmarks; B0 and B1
        # unchanged. The primary order (ok before refusal) is untouched by it.
        m = _common()["mapping"]
        refusal = {"item_id": "r1", "source_rule_id": "CONV-X-1", "unit_id": "u01",
                   "relation": "", "record_verdict": "irregular", "confidence": "UNCERTAIN"}
        ok = {"item_id": "r2", "source_rule_id": "CONV-X-1", "unit_id": "u02",
              "relation": "", "record_verdict": "ok"}
        bad = {"item_id": "r3", "source_rule_id": "CONV-X-1", "unit_id": "u03",
               "relation": "", "record_verdict": "irregular"}
        cases = [([refusal, ok], "CLEAR", "UNDECIDED"), ([refusal, ok, bad], "FLAG", "FLAG"),
                 ([ok], "CLEAR", "CLEAR"), ([refusal], "UNDECIDED", "UNDECIDED"), ([], "CLEAR", "CLEAR")]
        for name in NAMES:
            spec = _adapter(name).SPEC
            for records, primary, s5 in cases:
                run = {"failure": False, "records": records, "pairing_refusals": []}
                if name == "cuad" and primary == "FLAG":
                    primary = s5 = "CLEAR"      # an irregular record with no missing_field is present
                got = (m.classify(spec, "CONV-X-1", run)["class"],
                       m.classify(spec, "CONV-X-1", run, refusal_first=True)["class"])
                self.assertEqual(got, (primary, s5), "%s %d records" % (name, len(records)))
            row = m.classify(spec, "CONV-X-1", {"failure": False, "records": [refusal, ok],
                                                 "pairing_refusals": []})
            self.assertTrue(row["ok_over_refusal"], name)
            # S4 tie-break item b: a failed run decides nothing, so an ok record against a
            # refusal in it is no item decided by ok over refusal; the item abstains
            row = m.classify(spec, "CONV-X-1", {"failure": True, "records": [refusal, ok],
                                                 "pairing_refusals": []})
            self.assertEqual((row["class"], row["basis"], row["ok_over_refusal"]),
                             ("ABSTAIN", "run_failure", False), name)
        # through the label command: a failed run holding a refusal and an ok record for its
        # item adds nothing to items_decided_by_ok_over_refusal
        c = _common()
        cases = _json(_fixture("contractnli", "mapping_cases.json"))
        cases["runs"]["c-fail"]["review_data"]["findings"] = [
            dict(refusal, source_rule_id="CONV-CNLI-NDA-1"), dict(ok, source_rule_id="CONV-CNLI-NDA-1")]
        items, runs, _ = _materialise(cases, self.root / "failed")
        primary = c["cli"].label(_adapter("contractnli"), items, "B2", runs)["primary"]
        failed = next(r for r in primary["labels"] if r["item_id"] == "n-e")
        self.assertEqual((failed["class"], failed["basis"]), ("ABSTAIN", "run_failure"))
        self.assertEqual(primary["counts"]["items_decided_by_ok_over_refusal"], 1,
                         "only n-c, in the completed run")
        # through the label command: an S-5 analysis beside the others; B0 and B1 unchanged
        c = _common()
        cases = _json(_fixture("contractnli", "mapping_cases.json"))
        items, runs, b1 = _materialise(cases, self.root / "s5")
        b2 = c["cli"].label(_adapter("contractnli"), items, "B2", runs)
        self.assertEqual(sorted(b2), ["S-1", "S-2", "S-3", "S-5", "S-6", "S-7", "S-8", "primary"])
        for arm, folder in (("B1", b1), ("B0", None)):
            labels = c["cli"].label(_adapter("contractnli"), items, arm, folder)
            self.assertEqual([r["class"] for r in labels["S-5"]["labels"]],
                             [r["class"] for r in labels["primary"]["labels"]], arm)

    def test_catch_layer_reads_the_written_by_stamp(self):
        # Section 3.6 (D-039 item 16): the WRITTEN-BY-A stamp alone decides the layer,
        # compared exactly: `python` is Python's; any other stamp, and no stamp at all, is a
        # model's, whatever else the record carries (`model: python`, `absence_path`).
        m = _common()["mapping"]
        spec = _adapter("findver").SPEC
        cases = [({"written_by": "python"}, "computed"),
                 ({"written_by": "Python"}, "judged"),
                 ({"written_by": "python "}, "judged"),
                 ({"written_by": "model", "model": "python", "absence_path": "computed"}, "judged"),
                 ({"model": "python", "absence_path": "computed", "provenance": "computed"}, "judged"),
                 ({"model": "fixture-reader"}, "judged")]
        for extra, layer in cases:
            record = dict({"item_id": "r", "source_rule_id": "CONV-X-1", "unit_id": "u01-p-00001",
                           "relation": "sum_mismatch", "record_verdict": "irregular"}, **extra)
            run = {"failure": False, "records": [record], "pairing_refusals": []}
            row = m.classify(spec, "CONV-X-1", run)
            self.assertEqual((row["class"], row["layer"]), ("FLAG", layer), str(extra))


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
        self.assertEqual(h["headline_value"], h["accuracy"]["accuracy"])
        self.assertAlmostEqual(h["contradictory"]["precision"], 0.5)
        self.assertAlmostEqual(h["contradictory"]["recall"], 1 / 3)
        self.assertAlmostEqual(h["contradictory"]["f1"], 0.4)
        # SciTab. supports: tp 2 fp 0 fn 1 -> F1 0.8; refutes: tp 1 fp 1 fn 1 -> 0.5;
        # not enough info: tp 1 fp 1 fn 1 (ABSTAIN) -> 0.5; macro (0.8 + 0.5 + 0.5) / 3 = 0.6
        s, r, n = "supports", "refutes", "not enough info"
        h = _adapter("scitab").headline([(s, s), (s, s), (r, s), (n, r), (r, r), (A, n), (n, n)])
        self.assertAlmostEqual(h["macro_f1"], 0.6)
        self.assertEqual((h["headline_measure"], h["headline_value"]),
                         ("macro-F1 over supports, refutes, not enough info", h["macro_f1"]))
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
        self.assertEqual(h["headline_value"], h["macro_f1"])
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
        self.assertEqual(h["headline_value"], h["accuracy"]["accuracy"])
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
        # D-039 item 6: the headline is accuracy over all items; the two F1 are reported.
        self.assertEqual((h["headline_measure"], h["headline_value"]),
                         ("accuracy over all items, ABSTAIN counted wrong", 0.5))
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
        self.assertEqual(result["headline"]["evidence_containment_multi_unit"]["marked"], 2)
        self.assertEqual(result["location"]["flag_items_measurable_in_one_unit_documents"], 0)
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
        # ContraDoc marks sentences, not parts: a quote that only contains 205's evidence
        # unit's text does not locate it there (D-039 item 10 is for unit-marked benchmarks).
        self.assertFalse(adapter.SPEC.unit_evidence)
        # A one-unit contradictory document: B3 citing its one unit is located, and its
        # evidence counts in the all-documents containment but not the multi-unit one.
        one = self.root / "one.json"
        one.write_text(json.dumps({"pos": {"601": {"unique id": "601", "text": "It is noon. It is midnight.",
                                                   "evidence": "It is midnight."}}}), encoding="utf-8")
        _build("contradoc", self.root / "one", one)
        single = {"item_id": c["ids"].opaque_item_id("contradoc", "601"),
                  "document_id": c["ids"].opaque_document_id("contradoc", "601"), "rule_id": "CONV-CDOC-01",
                  "arm": "B3", "class": "FLAG", "label": "contradictory", "basis": "fixture",
                  "cited_unit_ids": ["u01-p-00001"], "layer": "judged", "evidence": None, "faults": []}
        result = c["metrics"].score_arm(adapter.SPEC, dict(labels, labels=[single]), self.root / "one",
                                        adapter.headline)
        self.assertEqual((result["headline"]["evidence_containment"]["marked"],
                          result["headline"]["evidence_containment_multi_unit"]["marked"],
                          result["location"]["flag_items_measurable_in_one_unit_documents"]), (1, 0, 1))
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

    def test_b1_location_on_a_benchmark_that_marks_parts(self):
        # D-039 item 10: on ContractNLI (and FinDVer), B1 is located if a quoted sentence,
        # whitespace-normalised, lies in an evidence unit, contains one, or lies in the
        # evidence units' texts joined in order. 7101's nda-2 is Contradiction with its
        # evidence in part 4 ("with its employees who need to know it."), a span shorter
        # than the sentence it ends, which begins in part 3.
        c = _common()
        adapter = _adapter("contractnli")
        self.assertTrue(adapter.SPEC.unit_evidence and _adapter("findver").SPEC.unit_evidence)
        _build("contractnli", self.root / "b")
        doc = c["ids"].opaque_document_id("contractnli", 7101)
        item = c["ids"].opaque_item_id("contractnli", "7101:nda-2")
        rows = {a["item_id"]: a for a in _json(self.root / "b" / doc / "answer_key.json")["items"]}
        self.assertEqual(rows[item]["evidence_unit_ids"], ["u04-p-00004"])

        def score(evidence):
            labels = []
            for answer in rows.values():
                label = {"item_id": answer["item_id"], "document_id": doc, "rule_id": answer["rule_id"],
                         "arm": "B1", "class": "CLEAR", "label": "entailment", "basis": "fixture",
                         "cited_unit_ids": [], "layer": "", "evidence": None, "faults": []}
                if answer["item_id"] == item:
                    label.update({"class": "FLAG", "label": "contradiction", "evidence": evidence})
                labels.append(label)
            other = c["ids"].opaque_document_id("contractnli", 7102)
            labels += [{"item_id": a["item_id"], "document_id": other, "rule_id": a["rule_id"], "arm": "B1",
                        "class": "CLEAR", "label": "entailment", "basis": "fixture", "cited_unit_ids": [],
                        "layer": "", "evidence": None, "faults": []}
                       for a in _json(self.root / "b" / other / "answer_key.json")["items"]]
            result = c["metrics"].score_arm(adapter.SPEC, {"arm": "B1", "labels": labels, "documents": [],
                                                           "counts": {"refusals": 0, "run_failure_documents": 0}},
                                            self.root / "b", adapter.headline)
            return result["location"]
        # 7102 holds the other measurable Contradiction item, labelled CLEAR here: 1 of 2.
        sentence = "The receiving party may share confidential information with its employees who need to know it."
        location = score(sentence)
        self.assertEqual((location["value"], location["flag_items_measurable"]), (0.5, 2))
        self.assertEqual(score("with its   employees who need")["value"], 0.5)
        self.assertEqual(score("The orchard is green.")["value"], 0.0)
        # Adversarial round 3, item 6: the reverse branch (a quoted sentence containing an
        # evidence unit's text) needs a unit text of at least REVERSE_CONTAINMENT_MIN_WORDS
        # words (5). Part 4 holds 8 words; with the minimum raised above 8 the same sentence
        # no longer locates the item, while a quote inside the unit still does.
        self.assertEqual(c["metrics"].REVERSE_CONTAINMENT_MIN_WORDS, 5)
        with mock.patch.object(c["metrics"], "REVERSE_CONTAINMENT_MIN_WORDS", 9):
            self.assertEqual(score(sentence)["value"], 0.0)
            self.assertEqual(score("with its   employees who need")["value"], 0.5)
        with mock.patch.object(c["metrics"], "REVERSE_CONTAINMENT_MIN_WORDS", 8):
            self.assertEqual(score(sentence)["value"], 0.5)

    def test_cut_sensitivity_leaves_out_items_with_evidence_beyond_the_cut(self):
        # S-4 (section 5.3, D-039 item 8): the primary labels without the items parts.json
        # lists as having their marked evidence beyond the cut; the count is in every arm's
        # score. ContraDoc 101's evidence sentence is in its cut third part.
        c = _common()
        adapter = _adapter("contradoc")
        _build("contradoc", self.root / "cut", max_context=198, output_allowance=10,
               token_counter=WordCounter(100))
        items = self.root / "cut" / "items.json"
        result = c["cli"].score(adapter, c["cli"].label(adapter, items, "B0"), self.root / "cut")
        self.assertEqual(sorted(result), ["S-1", "S-2", "S-3", "S-4", "S-5", "S-6", "S-7", "S-8", "primary"])
        self.assertEqual((result["primary"]["decisions"], result["S-4"]["decisions"]), (4, 3))
        self.assertEqual((result["primary"]["items_evidence_beyond_cut"],
                          result["S-4"]["items_evidence_beyond_cut"]), (1, 0))
        self.assertEqual(result["S-4"]["analysis"], "S-4")


# ---------------------------------------------------------------------------
# the command line, from a copied tree, in an isolated interpreter


_COUNTER = '''"""A stand-in token counter for the cut budget: one token per word."""


def count(text):
    return len(text.split())


def count_prompt(system, user):
    return len((system + " " + user).split())
'''


class CliChecks(_Case):
    """Adversarial round 2, item 9: the command line wiring, run as role B runs it: the
    adapters copied out of the repository with the B1 prompt beside them, in a fresh
    interpreter with `-I` (no script directory, no user site, no environment), so the
    repository's scripts/ cannot be on the path."""

    def setUp(self):
        super().setUp()
        self.tree = self.root / "copy" / "benchmark"
        shutil.copytree(ADAPTERS, self.tree / "adapters",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (self.tree / "baselines").mkdir()
        shutil.copy2(ROOT / "benchmark" / "baselines" / "b1_prompt.json", self.tree / "baselines")
        self.counter = self.root / "counter.py"
        self.counter.write_text(_COUNTER, encoding="utf-8")

    def _cli(self, name, *args):
        out = subprocess.run([sys.executable, "-I", "-X", "utf8", str(self.tree / "adapters" / name / "adapter.py")]
                             + [str(a) for a in args], capture_output=True, text=True, encoding="utf-8",
                             cwd=str(self.root), timeout=300)
        return out.returncode, out.stdout, out.stderr

    def test_findver_build_from_a_copied_tree(self):
        fixtures = self.tree / "adapters" / "findver" / "fixtures"
        out = self.root / "out"
        code, stdout, stderr = self._cli(
            "findver", "build", "--input", fixtures / "data" / "testmini.json", "--out", out,
            "--side", "development", "--max-context", 5000, "--output-allowance", 10,
            "--token-counter", self.counter, "--reports", fixtures / "financial_reports")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["documents"], 2)
        record = _json(out / "parts.json")
        self.assertEqual(record["cut_inputs"]["token_counter_sha256"],
                         hashlib.sha256(self.counter.read_bytes()).hexdigest())
        self.assertEqual(record["cut_inputs"]["b1_prompt_sha256"], hashlib.sha256(
            (self.tree / "baselines" / "b1_prompt.json").read_bytes()).hexdigest())
        self.assertEqual({d["side"] for d in record["documents"]}, {"development"})
        doc = _common()["ids"].opaque_document_id("findver", "ZQY-WT-2024-02-29_10-Q.json")
        text = (out / doc / "context" / (doc + ".md")).read_text(encoding="utf-8")
        self.assertIn("| Region | Staff |\n| :--- | ---: |\n| North | 12 |", text)
        self.assertEqual(text.count("| :--- | ---: |"), 1)
        # The adapter's own option reaches it: an empty reports folder holds no filing.
        empty = self.root / "empty"
        empty.mkdir()
        code, _out, stderr = self._cli(
            "findver", "build", "--input", fixtures / "data" / "testmini.json", "--out", self.root / "o2",
            "--development", "--reports", empty)
        self.assertEqual((code, "no filing" in stderr), (4, True), stderr)
        # An option another adapter takes is not one of FinDVer's.
        code, _out, stderr = self._cli(
            "findver", "build", "--input", fixtures / "data" / "testmini.json", "--out", self.root / "o3",
            "--development", "--frozen-sha256", "0" * 64)
        self.assertEqual(code, 2, stderr)
        self.assertIn("unrecognized arguments", stderr)
        with self.assertRaisesRegex(ValueError, "options this adapter does not take: parts"):
            _common()["cli"].build(_adapter("findver"), _source("findver"), self.root / "o4",
                                   development=True, synthetic=True, parts="span")

    def test_bands_and_split_from_a_copied_tree(self):
        fixtures = self.tree / "adapters" / "contradoc" / "fixtures"
        code, _stdout, stderr = self._cli("contradoc", "split", "--input", fixtures / "synthetic_items.json",
                                          "--out", self.root / "split.json")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(_json(self.root / "split.json")["documents"]), 4)
        self.assertNotIn(str(ROOT / "scripts"), stderr)
        # ContraDoc's bands read the frozen split file alone; without it they are refused
        code, _stdout, stderr = self._cli("contradoc", "bands", "--input", fixtures / "synthetic_items.json",
                                          "--out", self.root / "refused.json")
        self.assertEqual((code, "needs --assignment" in stderr), (4, True), stderr)
        self.assertFalse((self.root / "refused.json").exists())
        code, stdout, stderr = self._cli("contradoc", "bands", "--input", fixtures / "synthetic_items.json",
                                         "--assignment", self.root / "split.json",
                                         "--out", self.root / "bands.json")
        self.assertEqual(code, 0, stderr)
        printed = json.loads(stdout)
        self.assertEqual(sum(b["documents"] for key in ("holdout_pool_bands", "development_bands")
                             for b in printed[key].values()), 4)
        self.assertEqual(len(_json(self.root / "bands.json")["documents"]), 4)

    def _budget(self):
        return ["--max-context", 5000, "--output-allowance", 10, "--token-counter", self.counter]

    def test_scitab_and_cuad_builds_with_exclude_from_a_copied_tree(self):
        # Adversarial round 3, item 9: the SciTab and CUAD builds and --exclude through the
        # command line. The SciTab fixture holds two holdout tables and one development
        # table; listing the development one makes a holdout build possible, and parts.json
        # records the list's SHA-256 and what it removed.
        fixtures = self.tree / "adapters" / "scitab" / "fixtures"
        listed = self.root / "exclude.json"
        listed.write_text(json.dumps({"source_document_ids": ["syn-tab-3"]}), encoding="utf-8")
        code, _out, stderr = self._cli("scitab", "build", "--input", fixtures / "synthetic_items.json",
                                       "--out", self.root / "s1", "--side", "holdout", *self._budget())
        self.assertEqual((code, "not on the declared side holdout" in stderr), (4, True), stderr)
        code, stdout, stderr = self._cli("scitab", "build", "--input", fixtures / "synthetic_items.json",
                                         "--out", self.root / "s2", "--side", "holdout", "--exclude", listed,
                                         *self._budget())
        self.assertEqual(code, 0, stderr)
        record = _json(self.root / "s2" / "parts.json")
        self.assertEqual(sorted(d["source_document_id"] for d in record["documents"]), ["syn-tab-1", "syn-tab-2"])
        self.assertEqual([r["source_document_id"] for r in record["excluded_documents"]], ["syn-tab-3"])
        self.assertEqual(record["exclusion_sha256"], hashlib.sha256(listed.read_bytes()).hexdigest())
        cuad = self.tree / "adapters" / "cuad" / "fixtures" / "synthetic_items.json"
        code, stdout, stderr = self._cli("cuad", "build", "--input", cuad, "--out", self.root / "c",
                                         "--side", "holdout", *self._budget())
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["documents"], 2)
        self.assertEqual(len(_json(self.root / "c" / "items.json")["items"]), 2 * 41)

    def test_contractnli_frozen_file_and_merged_parts_from_a_copied_tree(self):
        # Adversarial round 3, item 9: --frozen-sha256 and --parts merged through the command
        # line. The fixture is no frozen development file, so a development build refuses
        # it; as a holdout input it is accepted only under its own SHA-256.
        fixture = self.tree / "adapters" / "contractnli" / "fixtures" / "synthetic_items.json"
        digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
        code, _out, stderr = self._cli("contractnli", "build", "--input", fixture, "--out", self.root / "d",
                                       "--side", "development", *self._budget())
        self.assertEqual((code, "not the frozen ContractNLI file" in stderr), (4, True), stderr)
        code, _out, stderr = self._cli("contractnli", "build", "--input", fixture, "--out", self.root / "w",
                                       "--side", "holdout", "--frozen-sha256", "0" * 64, *self._budget())
        self.assertEqual((code, "not the frozen ContractNLI file" in stderr), (4, True), stderr)
        code, stdout, stderr = self._cli("contractnli", "build", "--input", fixture, "--out", self.root / "h",
                                         "--side", "holdout", "--frozen-sha256", digest, "--parts", "merged",
                                         *self._budget())
        self.assertEqual(code, 0, stderr)
        record = _json(self.root / "h" / "parts.json")
        self.assertEqual(record["input_check"], {"input_sha256": digest, "frozen_for": "holdout"})
        self.assertEqual({(d["part_rule"], d["side"]) for d in record["documents"]}, {("merged", "holdout")})
        code, stdout, stderr = self._cli("contractnli", "bands", "--input", fixture, "--frozen-sha256", digest)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["documents_by_side"], {"holdout": 2})


# ---------------------------------------------------------------------------
# the one record reader (common/records.py; loop plan S5, R22 and item 0.8)


_MODEL_BACKEND, _MODEL_ID = "local_producer", "fixture-reader"


def _bus_line(agent, doc_id, items, backend, model, **body):
    return json.dumps({"timestamp": "2026-10-28T00:00:00+00:00", "sender": agent,
                       "sender_role": "agent", "recipient": "ORCHESTRATOR", "channel": "main",
                       "type": "INFORM", "uncertain": False,
                       "body": dict({"event": "AGENT_OUTPUT", "backend": backend, "model": model,
                                     "item_count": len(items),
                                     "payload": {"agent": agent, "doc_id": doc_id, "items": items}},
                                    **body)})


def _as_bus(run_dir, doc_id, judged_raw=None):
    """Move one run folder's review_data.json findings onto a bus, as the pipeline posts
    them: Python's records (stamped python) in one paired/python line, every other record
    in one model line with a call id; no item keeps its own `written_by`. A judged-absence
    raw copy, if given, goes in a line whose call id the pairing map names as a judged-absence
    call, and a record for another document in a line of its own. The review_data.json is
    removed, so only the bus holds the records."""
    path = Path(run_dir) / "deliverables" / doc_id / "review_data.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    path.unlink(missing_ok=True)
    bus = Path(run_dir) / "logs" / "agent_bus.jsonl"
    if not isinstance(data, dict):
        return 0      # unreadable or missing: no bus either, a run failure both ways
    bus.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(data.get("findings"), list):
        bus.write_text("", encoding="utf-8")
        return 0      # no typed records: silent both ways
    strip = lambda r: {k: v for k, v in r.items() if k != "written_by"}  # noqa: E731
    python = [strip(r) for r in data["findings"] if r.get("written_by") == "python"]
    model = [strip(r) for r in data["findings"] if r.get("written_by") != "python"]
    lines = [_bus_line("PRACTICE_AUDITOR", doc_id, python, "paired", "python"),
             _bus_line("PRACTICE_AUDITOR", doc_id, model, _MODEL_BACKEND, _MODEL_ID,
                       call_id="c" * 32),
             _bus_line("PRACTICE_AUDITOR", "another-document",
                       [dict(r, record_verdict="irregular") for r in data["findings"]],
                       _MODEL_BACKEND, _MODEL_ID)]
    if judged_raw:
        lines.append(_bus_line("PRACTICE_AUDITOR", doc_id, judged_raw, _MODEL_BACKEND, _MODEL_ID,
                               call_id="a" * 32))
        pairing_path = Path(run_dir) / "audit" / "pairing_map.json"
        pairing_path.parent.mkdir(exist_ok=True)
        pairing = json.loads(pairing_path.read_text(encoding="utf-8")) if pairing_path.is_file() else {}
        mine = pairing.setdefault(doc_id, {})
        mine.setdefault("judging_calls", []).append(
            {"call_id": "a" * 32, "agent": "PRACTICE_AUDITOR", "plan_kind": "absence_judged",
             "outcome": "judged_absence"})
        pairing_path.write_text(json.dumps(pairing), encoding="utf-8")
    bus.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(judged_raw or [])


def _label_view(result):
    return {r["item_id"]: (r["class"], r["label"], r["basis"], r["cited_unit_ids"], r["layer"],
                           r["figure_audit_set_aside"], r["s3"]["class"], r["s5"]["class"])
            for r in result["labels"]}


class RecordReaderChecks(_Case):
    """R22: one record reader for both forms. B2 is read from review_data.json, B3 from the
    run's bus; the bus stamps written_by from the line, supersedes within (agent, document,
    item_id) on the highest revision, counts a judged absence only by Python's stamped copy
    and lists the raw model copy apart. The same records in both forms give the same labels."""

    def test_same_records_in_both_forms_give_the_same_labels(self):
        c = _common()
        m, rec = c["mapping"], c["records"]
        compared = 0
        for name in NAMES:
            adapter = _adapter(name)
            cases = _json(_fixture(name, "mapping_cases.json"))
            items, runs, _ = _materialise(cases, self.root / name / "rd")
            _ignored, bus_runs, _ = _materialise(cases, self.root / name / "bus")
            listed = 0
            for doc in cases["runs"]:
                rules = sorted({i["rule_id"] for i in cases["items"] if i["document_id"] == doc})
                # a raw judged-absence copy saying every rule's field is absent: never counted
                raw = [{"item_id": "raw-%d" % k, "source_rule_id": rule, "unit_id": "u01-p-00001",
                        "relation": "missing_field", "record_verdict": "irregular",
                        "absence_path": "judged"} for k, rule in enumerate(rules)]
                listed += _as_bus(bus_runs / doc, doc, judged_raw=raw)
            rows = m.read_items(items)
            by_review = m.label_pipeline_arm(adapter.SPEC, rows, runs, arm="B2")
            by_bus = m.label_pipeline_arm(adapter.SPEC, rows, bus_runs, arm="B3")
            self.assertEqual(_label_view(by_bus), _label_view(by_review), name)
            self.assertEqual({d["document_id"]: d["run_failure"] for d in by_bus["documents"]},
                             {d["document_id"]: d["run_failure"] for d in by_review["documents"]}, name)
            self.assertEqual({d["record_source"] for d in by_bus["documents"]}, {rec.BUS}, name)
            self.assertEqual({d["record_source"] for d in by_review["documents"]}, {rec.REVIEW_DATA}, name)
            self.assertGreater(listed, 0, name)
            self.assertEqual(by_bus["counts"]["raw_judged_absence_records"], listed, name)
            self.assertEqual(by_review["counts"]["raw_judged_absence_records"], 0, name)
            compared += len(by_bus["labels"])
        self.assertGreater(compared, 20)

    def test_bus_rules(self):
        rec, m = _common()["records"], _common()["mapping"]
        spec = _adapter("cuad").SPEC
        doc, rule = "dx", "CONV-X-01"
        run = self.root / "run"
        (run / "audit").mkdir(parents=True)
        (run / "audit" / "run_completion.json").write_text(json.dumps({
            "schema_version": 1, "state": "completed", "reached_end": True, "exit_code": 0,
            "finished_at": "2026-10-28T00:00:00+00:00"}), encoding="utf-8")
        (run / "audit" / "pairing_map.json").write_text(json.dumps({doc: {"judging_calls": [
            {"call_id": "a" * 32, "plan_kind": "absence_judged"},
            {"call_id": "e" * 32, "plan_kind": "uncomputable"}]}}), encoding="utf-8")

        def r(item_id, verdict="irregular", **extra):
            return dict({"item_id": item_id, "source_rule_id": rule, "unit_id": "u01-p-00001",
                         "relation": "sum_mismatch", "record_verdict": verdict}, **extra)
        lines = [
            # written_by from the line: an item's own stamp is replaced
            _bus_line("A1", doc, [r("p1", written_by="model")], "paired", "python"),
            _bus_line("A1", doc, [r("m1", written_by="python")], "local_producer", "qwen"),
            _bus_line("A1", doc, [r("p2")], "computed", "python-x"),
            _bus_line("A1", doc, [r("m2")], "paired", "qwen"),
            # supersession within (agent, document, item_id): highest revision, then ts, then line
            _bus_line("A1", doc, [r("s1", "irregular", revision=2)], "paired", "python"),
            _bus_line("A1", doc, [r("s1", "ok", revision=1)], "paired", "python"),
            _bus_line("A2", doc, [r("s1", "ok", revision=1)], "paired", "python"),
            _bus_line("A1", doc, [r("t1", "ok", revision=1, ts="2026-10-28T02:00:00")], "paired", "python"),
            _bus_line("A1", doc, [r("t1", "irregular", revision=1, ts="2026-10-28T01:00:00")], "paired", "python"),
            _bus_line("A1", doc, [r("l1", "irregular")], "paired", "python"),
            _bus_line("A1", doc, [r("l1", "ok")], "paired", "python"),
            # a judged absence: the raw copy (call named by the pairing map, or by a bus
            # line's judging_calls) listed apart; Python's stamped copy counted
            _bus_line("J", doc, [r("raw1", relation="missing_field", absence_path="judged")],
                      "local_producer", "qwen", call_id="a" * 32),
            _bus_line("J", doc, [r("raw2", relation="missing_field")], "local_producer", "qwen",
                      call_id="b" * 32),
            json.dumps({"body": {"event": "PAIRED_JUDGING_CALLS", "backend": "paired", "model": "python",
                                 "doc_id": doc, "judging_calls": [{"call_id": "b" * 32,
                                                                   "plan_kind": "absence_judged"}]}}),
            _bus_line("J", doc, [r("J:finding:u01-p-00001:CONV-001:1", relation="missing_field",
                                   absence_path="judged", revision=1)], "local_producer", "qwen",
                      stamped_by="python", absence_path="judged"),
            # a model reply to another judging call is a model's record like any other
            _bus_line("J", doc, [r("u1", "ok")], "local_producer", "qwen", call_id="e" * 32),
            # not records: no record_verdict and no refusal; another document; a broken line
            _bus_line("A1", doc, [{"item_id": "x1", "source_rule_id": rule, "claim": "c"}], "qwen", "qwen"),
            _bus_line("A1", "other", [r("o1")], "paired", "python"),
            "{not json",
            # a refusal with no relation that names its rule is a record
            _bus_line("A3", doc, [{"item_id": "f1", "source_rule_id": rule, "confidence": "uncertain"}],
                      "local_producer", "qwen"),
        ]
        (run / "logs").mkdir()
        (run / "logs" / "agent_bus.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        read = rec.read_records(run, doc, rec.BUS)
        got = {(r.get("item_id"), r.get("record_verdict"), r["written_by"]) for r in read["records"]}
        self.assertEqual(got, {
            ("p1", "irregular", "python"), ("m1", "irregular", "model"),
            ("p2", "irregular", "python"), ("m2", "irregular", "model"),
            ("s1", "irregular", "python"), ("s1", "ok", "python"),
            ("t1", "ok", "python"), ("l1", "ok", "python"),
            ("J:finding:u01-p-00001:CONV-001:1", "irregular", "model"),
            ("u1", "ok", "model"), ("f1", None, "model")})
        self.assertEqual(sorted(r["item_id"] for r in read["raw_judged_absence"]), ["raw1", "raw2"])
        self.assertEqual(read["faults"], ["bus_lines_unreadable:1"])
        self.assertEqual(read["failure_reasons"], [])
        # the stamped judged copy decides CUAD's absent class; the raw copies decide nothing
        run_view = m.read_run(run, doc, rec.BUS)
        absent = [x for x in run_view["records"] if x.get("relation") == "missing_field"]
        self.assertEqual([x["item_id"] for x in absent], ["J:finding:u01-p-00001:CONV-001:1"])
        self.assertEqual(m.classify(spec, rule, run_view, rule_count=41)["basis"], "irregular_missing_field")
        # a missing bus is a run failure; review_data.json is not read for B3
        (run / "logs" / "agent_bus.jsonl").unlink()
        self.assertEqual(m.read_run(run, doc, rec.BUS)["failure_reasons"], ["bus_missing"])
        with self.assertRaises(ValueError):
            rec.read_records(run, doc, "elsewhere")

    def test_label_command_labels_b3_from_the_bus_once_adopted(self):
        # D-056: the bus reading is adopted, so the label command labels B3 (and B4) from a
        # run's bus, giving the labels the same records give B2 from review_data.json; with
        # the flag off it still refuses, as before the adoption.
        c = _common()
        self.assertTrue(c["mapping"].BUS_READER_ADOPTED)
        self.assertEqual(c["mapping"].RECORD_SOURCE, {"B2": "review_data", "B3": "bus", "B4": "bus"})
        for name in NAMES:
            cases = _json(_fixture(name, "mapping_cases.json"))
            items, runs, _ = _materialise(cases, self.root / name / "rd")
            _ignored, bus_runs, _ = _materialise(cases, self.root / name / "bus")
            for doc in cases["runs"]:
                _as_bus(bus_runs / doc, doc)
            by_review = c["cli"].label(_adapter(name), items, "B2", runs)
            for arm in ("B3", "B4"):
                by_bus = c["cli"].label(_adapter(name), items, arm, bus_runs)
                self.assertEqual(_label_view(by_bus["primary"]), _label_view(by_review["primary"]), name + " " + arm)
                self.assertTrue(by_bus["primary"]["labels"], name)
                self.assertEqual(sorted(by_bus), ["S-1", "S-2", "S-3", "S-5", "S-6", "S-7", "S-8", "primary"])
            with mock.patch.object(c["mapping"], "BUS_READER_ADOPTED", False):
                with self.assertRaisesRegex(c["mapping"].Refused, "bus"):
                    c["cli"].label(_adapter(name), items, "B3", bus_runs)


# ---------------------------------------------------------------------------
# D-066 (incomplete runs, completeness, S-6, item_calls_failed) and D-068 records


_DONE = "2026-10-29T00:00:00+00:00"


def _incomplete_run(root, doc, *, completion, bus_lines, pairing=None, rule_map=None,
                    observation=None, telemetry=None):
    """One synthetic B3 run folder: its completion record, bus, pairing map, rule map and
    the two telemetry files the completeness report reads (absent when None)."""
    run = Path(root) / doc
    (run / "audit").mkdir(parents=True)
    (run / "logs").mkdir()
    (run / "audit" / "run_completion.json").write_text(json.dumps(completion), encoding="utf-8")
    (run / "logs" / "agent_bus.jsonl").write_text("\n".join(bus_lines) + "\n", encoding="utf-8")
    if pairing is not None:
        (run / "audit" / "pairing_map.json").write_text(json.dumps({doc: pairing}), encoding="utf-8")
    if rule_map is not None:
        (run / "audit" / "convention_assignment.json").write_text(json.dumps({"by_rule": {
            k: {"source_rule_id": v} for k, v in rule_map.items()}}), encoding="utf-8")
    for name, rows in (("generation_observation.jsonl", observation), ("model_telemetry.jsonl", telemetry)):
        if rows is not None:
            (run / "logs" / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return run


def _completion(state="completed", **extra):
    return dict({"schema_version": 1, "state": state, "reached_end": True, "exit_code": 0,
                 "finished_at": _DONE}, **extra)


def _rec(item_id, rule, verdict, unit="u01-p-00001", **extra):
    return dict({"item_id": item_id, "source_rule_id": rule, "unit_id": unit, "relation": "date_window",
                 "record_verdict": verdict}, **extra)


class IncompleteRunChecks(_Case):
    """D-066 and D-068 in the adapters, each property by neutralise, fail, restore, pass."""

    def _items(self, doc, rules):
        return [{"item_id": "i-%s-%d" % (doc, k), "document_id": doc, "rule_id": rule, "benchmark": "contractnli"}
                for k, rule in enumerate(rules)]

    def _proof(self, body, neutralise):
        self.assertEqual(body(), [], "shipped")
        with neutralise():
            self.assertNotEqual(body(), [], "neutralised, the proof still passed")
        self.assertEqual(body(), [], "restored")

    def test_a_semantically_incomplete_end_is_labelled_from_its_records(self):
        m = _common()["mapping"]
        spec = _adapter("contractnli").SPEC
        rules = ["CONV-CNLI-NDA-1", "CONV-CNLI-NDA-2", "CONV-CNLI-NDA-3"]
        lines = [_bus_line("A", "dinc", [_rec("r1", rules[0], "irregular"), _rec("r2", rules[1], "ok")],
                           "paired", "python")]
        root = self.root / "inc"
        _incomplete_run(root, "dinc", completion=_completion("stopped", semantic_complete=False), bus_lines=lines)
        # a stopped run that did not reach its end, and one with exit code 2, are still run failures
        _incomplete_run(root, "dstop", completion=_completion("stopped", reached_end=False, semantic_complete=False),
                        bus_lines=[_bus_line("A", "dstop", [_rec("r1", rules[0], "irregular")], "paired", "python")])
        _incomplete_run(root, "dexit", completion=_completion("stopped", exit_code=2, semantic_complete=False),
                        bus_lines=[_bus_line("A", "dexit", [_rec("r1", rules[0], "irregular")], "paired", "python")])
        items = self._items("dinc", rules) + self._items("dstop", rules[:1]) + self._items("dexit", rules[:1])

        def body():
            out = m.label_pipeline_arm(spec, items, root, arm="B3")
            got = {r["item_id"]: (r["class"], r["basis"]) for r in out["labels"]}
            want = {"i-dinc-0": ("FLAG", "irregular"), "i-dinc-1": ("CLEAR", "ok"), "i-dinc-2": ("CLEAR", "silent"),
                    "i-dstop-0": ("ABSTAIN", "run_failure"), "i-dexit-0": ("ABSTAIN", "run_failure")}
            docs = {d["document_id"]: (d["run_failure"], d["semantic_incomplete"]) for d in out["documents"]}
            problems = [] if got == want else ["labels %s" % got]
            if docs != {"dinc": (False, True), "dstop": (True, False), "dexit": (True, False)}:
                problems.append("documents %s" % docs)
            if (out["counts"]["semantic_incomplete_documents"], out["counts"]["items_in_semantic_incomplete_documents"]) != (1, 3):
                problems.append("counts %s" % out["counts"])
            # S-6: every item of the semantically incomplete document ABSTAIN, the rest unchanged
            s6 = {r["item_id"]: (r["class"], r["basis"]) for r in m.sensitivity_s6(spec, out)["labels"]}
            want6 = dict(want, **{k: ("ABSTAIN", "s6_semantic_incomplete") for k in want if k.startswith("i-dinc")})
            if s6 != want6:
                problems.append("S-6 %s" % s6)
            return problems
        self._proof(body, lambda: mock.patch.object(m, "semantically_incomplete_end", lambda c: False))
        self._proof(body, lambda: mock.patch.object(
            m, "sensitivity_s6", lambda spec, result: m._relabel(spec, result, "S-6", lambda r: None)))
        # through the label command: S-6 beside the other analyses, B0 and B1 unchanged by it
        c = _common()
        path = self.root / "items.json"
        path.write_text(json.dumps({"items": items}), encoding="utf-8")
        labels = c["cli"].label(_adapter("contractnli"), path, "B3", root)
        self.assertEqual(sorted(labels), ["S-1", "S-2", "S-3", "S-5", "S-6", "S-7", "S-8", "primary"])
        b0 = c["cli"].label(_adapter("contractnli"), path, "B0")
        self.assertEqual([r["class"] for r in b0["S-6"]["labels"]], [r["class"] for r in b0["primary"]["labels"]])

    def test_item_calls_failed_applies_through_the_rule_map(self):
        # Open point 12.11, adopted (D-078): a judging call names the registry id; the run's
        # own audit/convention_assignment.json (by_rule, source_rule_id) takes it to the
        # item's operator id, and an item no record decides whose rule's calls all failed is
        # ABSTAIN item_calls_failed. A map that is missing, unreadable or not one to one is
        # not used on that document: the row says why and the document is counted.
        m = _common()["mapping"]
        spec = _adapter("contractnli").SPEC
        rules = ["CONV-CNLI-NDA-1", "CONV-CNLI-NDA-2", "CONV-CNLI-NDA-3"]
        failed = {"outcome": "reply_failed", "plan_kind": "uncomputable"}
        pairing = {"judging_calls": [dict(failed, rule_id="CONV-001", call_id="a" * 32),
                                     dict(failed, rule_id="CONV-001", call_id="b" * 32),
                                     dict(failed, rule_id="CONV-002", call_id="c" * 32),
                                     {"outcome": "judged_uncomputable", "rule_id": "CONV-002", "call_id": "d" * 32},
                                     dict(failed, rule_id="CONV-003", call_id="e" * 32)]}
        rule_map = {"CONV-001": rules[0], "CONV-002": rules[1], "CONV-003": rules[2]}
        lines = [_bus_line("A", "dcall", [_rec("r3", rules[2], "irregular")], "paired", "python")]
        root = self.root / "calls"
        _incomplete_run(root, "dcall", completion=_completion(), bus_lines=lines, pairing=pairing, rule_map=rule_map)
        empty = lambda doc: [_bus_line("A", doc, [], "paired", "python")]  # noqa: E731
        _incomplete_run(root, "dnomap", completion=_completion(), bus_lines=empty("dnomap"), pairing=pairing)
        # two registry ids naming one operator id: not one to one, not used
        _incomplete_run(root, "dtwo", completion=_completion(), bus_lines=empty("dtwo"), pairing=pairing,
                        rule_map={"CONV-001": rules[0], "CONV-002": rules[0].lower(), "CONV-003": rules[2]})
        bad = _incomplete_run(root, "dbad", completion=_completion(), bus_lines=empty("dbad"), pairing=pairing)
        (bad / "audit" / "convention_assignment.json").write_text("{not json", encoding="utf-8")
        items = (self._items("dcall", rules) + self._items("dnomap", rules[:1])
                 + self._items("dtwo", rules[:1]) + self._items("dbad", rules[:1]))

        def view():
            out = m.label_pipeline_arm(spec, items, root, arm="B3")
            return ({r["item_id"]: (r["class"], r["basis"], r["item_calls_failed"]) for r in out["labels"]},
                    out["counts"]["item_calls_failed"], out["counts"]["item_calls_failed_not_applied"],
                    out["counts"]["documents_rule_map_unusable"],
                    {d["document_id"]: d["rule_map_status"] for d in out["documents"]})

        statuses = {"dcall": "ok", "dnomap": "missing", "dtwo": "not_one_to_one", "dbad": "unreadable"}

        def adopted():
            got = view()
            # all calls failed and no record decides: ABSTAIN; a record still decides; a
            # rule with one returned call is silent; a missing, unreadable or many-to-one
            # map: not applied, says why, the document counted
            want = ({"i-dcall-0": ("ABSTAIN", "item_calls_failed", "applied"),
                     "i-dcall-1": ("CLEAR", "silent", None),
                     "i-dcall-2": ("FLAG", "irregular", "applied"),
                     "i-dnomap-0": ("CLEAR", "silent", "not_applied_no_rule_map"),
                     "i-dtwo-0": ("CLEAR", "silent", "not_applied_rule_map_not_one_to_one"),
                     "i-dbad-0": ("CLEAR", "silent", "not_applied_rule_map_unreadable")}, 1, 0, 3, statuses)
            return [] if got == want else ["adopted %s" % (got,)]

        def unsettled():
            # the switch off (the S4 state): computed, reported, never applied
            with mock.patch.object(m, "RULE_ID_MAP_ADOPTED", False):
                got = view()
            want = ({"i-dcall-0": ("CLEAR", "silent", "not_applied_rule_map_unsettled:would_apply"),
                     "i-dcall-1": ("CLEAR", "silent", "not_applied_rule_map_unsettled"),
                     "i-dcall-2": ("FLAG", "irregular", "not_applied_rule_map_unsettled:would_apply"),
                     "i-dnomap-0": ("CLEAR", "silent", "not_applied_rule_map_unsettled"),
                     "i-dtwo-0": ("CLEAR", "silent", "not_applied_rule_map_unsettled"),
                     "i-dbad-0": ("CLEAR", "silent", "not_applied_rule_map_unsettled")}, 0, 2, 3, statuses)
            return [] if got == want else ["unsettled %s" % (got,)]

        def loose(run_dir):
            # a reader that takes the map as written, one to one or not
            path = Path(run_dir) / "audit" / "convention_assignment.json"
            try:
                by_rule = json.loads(path.read_text(encoding="utf-8"))["by_rule"]
            except (OSError, ValueError, KeyError):
                return {}, "ok"
            return {k.casefold(): v["source_rule_id"].casefold() for k, v in by_rule.items()}, "ok"
        self.assertTrue(m.RULE_ID_MAP_ADOPTED, "open point 12.11 is settled (D-078): the exception is applied")
        self._proof(adopted, lambda: mock.patch.object(m, "RULE_ID_MAP_ADOPTED", False))
        self._proof(adopted, lambda: mock.patch.object(m, "JUDGING_CALL_FAILED", "never"))
        self._proof(adopted, lambda: mock.patch.object(m, "read_rule_map", loose))
        self._proof(unsettled, lambda: mock.patch.object(m, "JUDGING_CALL_FAILED", "never"))

    def test_a_registry_id_refusal_maps_to_the_operator_id(self):
        # Open point 12.11 (D-078): a pairing-map refusal (absence_refused) names the
        # registry id under `rule_id`, as scripts/pipeline.py writes it; through the run's own
        # map it is a refusal for the item of that operator id (UNDECIDED: ContractNLI's
        # NotMentioned), and with no map in the run it matches no item (silent).
        m = _common()["mapping"]
        spec = _adapter("contractnli").SPEC
        rules = ["CONV-CNLI-NDA-1", "CONV-CNLI-NDA-2"]
        refusal = {"unit_id": "u01-p-00001", "rule_id": "CONV-002", "relation": "missing_field",
                   "reason": "absence claim supplies no quote"}
        pairing = {"absence_refused": [refusal]}
        root = self.root / "refused"
        _incomplete_run(root, "dmap", completion=_completion(), bus_lines=[_bus_line("A", "dmap", [], "paired", "python")],
                        pairing=pairing, rule_map={"CONV-001": rules[0], "CONV-002": rules[1]})
        _incomplete_run(root, "dnomap", completion=_completion(),
                        bus_lines=[_bus_line("A", "dnomap", [], "paired", "python")], pairing=pairing)
        items = self._items("dmap", rules) + self._items("dnomap", rules)

        def body():
            out = m.label_pipeline_arm(spec, items, root, arm="B3")
            got = {r["item_id"]: (r["class"], r["label"], r["basis"]) for r in out["labels"]}
            want = {"i-dmap-0": ("CLEAR", "entailment", "silent"),
                    "i-dmap-1": ("UNDECIDED", "not mentioned", "refusal"),
                    "i-dnomap-0": ("CLEAR", "entailment", "silent"),
                    "i-dnomap-1": ("CLEAR", "entailment", "silent")}
            problems = [] if got == want else ["labels %s" % got]
            if out["counts"]["refusals"] != 1:
                problems.append("refusals %s" % out["counts"]["refusals"])
            return problems
        self._proof(body, lambda: mock.patch.object(m, "RULE_ID_MAP_ADOPTED", False))
        self._proof(body, lambda: mock.patch.object(m, "PAIRING_RULE_FIELDS", ("source_rule_id",)))

    def test_completeness_is_reported_per_document(self):
        m = _common()["mapping"]
        spec = _adapter("contractnli").SPEC
        rules = ["CONV-CNLI-NDA-1", "CONV-CNLI-NDA-2"]
        observation = [
            {"agent": "PROCESSOR", "doc_id": "dpart", "call_id": "p1", "accepted_semantic_output": True},
            {"agent": "PROCESSOR", "doc_id": "dpart", "call_id": "p2", "accepted_semantic_output": True},
            {"agent": "PROCESSOR", "doc_id": "dpart", "call_id": "p3", "accepted_semantic_output": False},
            {"agent": "VERIFIER", "doc_id": "dpart", "call_id": "v1", "accepted_semantic_output": True},
            {"agent": "PROCESSOR", "doc_id": "other", "call_id": "p9", "accepted_semantic_output": True},
            {"event": "extraction_merge", "doc_id": "dpart", "complete": False, "item_count": 2,
             "missing_partitions": [2], "partition_calls": ["p1", "p2", "p3"]}]
        telemetry = [{"event": "auditor_pair", "delivery": "partial"}, {"event": "auditor_pair", "delivery": "partial"},
                     {"event": "auditor_pair", "delivery": "complete"}, {"event": "model_call", "agent": "PROCESSOR"}]
        lines = [_bus_line("VERIFIER", "dpart", [_rec("v1", rules[0], "irregular")], "local_auditor", "m"),
                 _bus_line("PRACTICE_AUDITOR", "dpart", [_rec("p1", rules[1], "ok")], "paired", "python")]
        root = self.root / "part"
        _incomplete_run(root, "dpart", completion=_completion("stopped", semantic_complete=False), bus_lines=lines,
                        observation=observation, telemetry=telemetry)
        _incomplete_run(root, "dnone", completion=_completion(), bus_lines=[_bus_line("A", "dnone", [], "paired", "python")])
        items = self._items("dpart", rules) + self._items("dnone", rules[:1])

        def body():
            out = m.label_pipeline_arm(spec, items, root, arm="B3")
            docs = {d["document_id"]: d["completeness"] for d in out["documents"]}
            want = {"dpart": {"semantic_complete": False, "processor_calls_made": 3, "processor_calls_accepted": 2,
                              "processor_delivery_partial": True, "partial_delivery_pairs": 2},
                    "dnone": {"semantic_complete": True, "processor_calls_made": None, "processor_calls_accepted": None,
                              "processor_delivery_partial": None, "partial_delivery_pairs": None}}
            marked = {r["item_id"]: r["decided_by_partial_delivery_record"] for r in out["labels"]}
            problems = [] if docs == want else ["completeness %s" % docs]
            if marked != {"i-dpart-0": True, "i-dpart-1": False, "i-dnone-0": False}:
                problems.append("marked %s" % marked)
            if out["counts"]["items_decided_by_partial_delivery_record"] != 1:
                problems.append("count %s" % out["counts"]["items_decided_by_partial_delivery_record"])
            return problems
        self._proof(body, lambda: mock.patch.object(m, "DRAFT_READERS", ()))
        self._proof(body, lambda: mock.patch.object(m, "PRODUCER_AGENT", "NOBODY"))

    def test_items_flagged_by_a_band_record_are_counted(self):
        # Preregistration section 12 item 3: a claim's figures read as a band (from the
        # rule's own text) can decide a FLAG; the items so decided are counted per arm.
        m = _common()["mapping"]
        rules = ["CONV-T-1", "CONV-T-2", "CONV-T-3"]
        lines = [_bus_line("A", "dband", [_rec("b1", rules[0], "irregular", relation="below_band"),
                                          _rec("b2", rules[1], "irregular"),
                                          _rec("b3", rules[2], "ok", relation="above_band")], "paired", "python")]
        root = self.root / "band"
        _incomplete_run(root, "dband", completion=_completion(), bus_lines=lines)
        items = self._items("dband", rules)

        def body():
            problems = []
            for name, flagged in (("contractnli", 1), ("scitab", 1), ("cuad", 0)):
                out = m.label_pipeline_arm(_adapter(name).SPEC, items, root, arm="B3")
                got = [r["flagged_by_band"] for r in out["labels"]]
                want = [True, False, False] if flagged else [False, False, False]
                if got != want or out["counts"]["items_flagged_by_band"] != flagged:
                    problems.append("%s %s %s" % (name, got, out["counts"]["items_flagged_by_band"]))
            return problems
        self._proof(body, lambda: mock.patch.object(m, "BAND_RELATIONS", ()))

    def test_a_kept_uncomputable_answer_decides_its_rule_as_a_models_record(self):
        # D-068 on the bus as the pipeline posts it: the call's own post withholds its items,
        # Python's stamped copy (stamped_by python, judged_path uncomputable) carries the kept
        # answer under the model's backend; it is read once, written by model, and decides.
        m, rec = _common()["mapping"], _common()["records"]
        spec = _adapter("contractnli").SPEC
        rule = "CONV-CNLI-NDA-1"
        kept = _rec("PRACTICE_AUDITOR:finding:u02-p-00002:CONV-001:0", rule, "irregular", unit="u02-p-00002",
                    relation="missing_field", judged_path="uncomputable", revision=1)
        lines = [_bus_line("PRACTICE_AUDITOR", "dkept", [], "local_auditor", "m", call_id="f" * 32,
                           items_withheld=1),
                 _bus_line("PRACTICE_AUDITOR", "dkept", [kept], "local_auditor", "m", stamped_by="python",
                           judged_path="uncomputable")]
        pairing = {"judging_calls": [{"call_id": "f" * 32, "plan_kind": "uncomputable", "rule_id": "CONV-001",
                                      "outcome": "judged_uncomputable", "judged_listed": 1}]}
        root = self.root / "kept"
        run = _incomplete_run(root, "dkept", completion=_completion(), bus_lines=lines, pairing=pairing)
        read = rec.read_records(run, "dkept", rec.BUS)
        self.assertEqual([(r["item_id"], r["written_by"]) for r in read["records"]], [(kept["item_id"], "model")])
        self.assertEqual(read["raw_judged_absence"], [])
        row = m.classify(spec, rule, m.read_run(run, "dkept", rec.BUS))
        self.assertEqual((row["class"], row["basis"], row["layer"]), ("FLAG", "irregular", "judged"))


# ---------------------------------------------------------------------------
# section 5.3 and open point 12.14 (D-078): B3 documents with a call over the model's context


def _reply_record(run_dir, sequence, agent, context):
    """One reply record as scripts/reply_records.py writes it (counts only, no text):
    `<run>/audit/model_replies/<sequence>_<call id>.json`, with `context` when given."""
    folder = Path(run_dir) / "audit" / "model_replies"
    folder.mkdir(parents=True, exist_ok=True)
    call_id = ("%032x" % sequence)
    record = {"schema_version": 1, "sequence": sequence, "call_id": call_id, "agent": agent,
              "backend": "local_producer", "model_id": "stand-in", "backend_ok": context is None
              or context.get("over_context") is not True, "payload": None, "reply": None}
    if context is not None:
        record["context"] = context
    (folder / ("%06d_%s.json" % (sequence, call_id))).write_text(json.dumps(record), encoding="utf-8")


def _ctx(prompt_tokens, limit, allowance=2048):
    return {"prompt_tokens": prompt_tokens, "max_new_tokens": allowance, "model_context": limit,
            "over_context": None if limit is None else prompt_tokens + allowance > limit}


class OverContextChecks(_Case):
    """Section 5.3 (D-058 condition v) and open point 12.14 (D-078), on a hand-written B3 run
    per document of a synthetic ContractNLI build: a document whose run has one reply record
    with `context.over_context` true is excluded from B3 (basis over_context_excluded,
    listed and counted), every analysis but S-7 leaves it out, S-7 scores its items ABSTAIN,
    and the paired view drops it for both arms; without the flag the labels are those of
    the same run with no reply records at all. Neutralise, fail, restore, pass."""

    def _proof(self, body, neutralise):
        self.assertEqual(body(), [], "shipped")
        with neutralise():
            self.assertNotEqual(body(), [], "neutralised, the proof still passed")
        self.assertEqual(body(), [], "restored")

    def _setup(self):
        c = _common()
        adapter = _adapter("contractnli")
        _build("contractnli", self.root / "b")
        items_path = self.root / "b" / "items.json"
        items = c["mapping"].read_items(items_path)
        docs = sorted({i["document_id"] for i in items})
        self.assertGreaterEqual(len(docs), 2, "the synthetic build needs two documents")
        by_doc = c["mapping"].by_document(items)
        over, fits = docs[0], docs[1:]
        runs = {}
        for name in ("flag", "noflag", "bare"):
            root = self.root / name
            for doc in docs:
                rules = [i["rule_id"] for i in by_doc[doc]]
                # one irregular and one ok record, so every document has decided items
                recs = [_rec("x1", rules[0], "irregular")] + ([_rec("x2", rules[1], "ok")] if len(rules) > 1 else [])
                run = _incomplete_run(root, doc, completion=_completion(),
                                      bus_lines=[_bus_line("A", doc, recs, "paired", "python")])
                if name == "bare":
                    continue
                _reply_record(run, 1, "PROCESSOR", _ctx(3000, 32768))
                _reply_record(run, 2, "VERIFIER", _ctx(1000, None))      # no stated context
                _reply_record(run, 3, "SPEECH_ACT_TAGGER", None)          # an older record
                if name == "flag" and doc == over:
                    _reply_record(run, 4, "SPEECH_ACT_TAGGER", _ctx(35340, 32768))
                    _reply_record(run, 5, "LEGAL_ANALYST", _ctx(36413, 32768))
                    _reply_record(run, 6, "LEGAL_ANALYST", _ctx(36413, 32768))
            runs[name] = root
        return c, adapter, items_path, by_doc, over, fits, runs

    def test_an_over_context_document_is_excluded_from_b3(self):
        c, adapter, items_path, by_doc, over, fits, runs = self._setup()
        m, cli = c["mapping"], c["cli"]
        n_over = len(by_doc[over])
        n_all = sum(len(v) for v in by_doc.values())

        def body():
            problems = []
            labels = cli.label(adapter, items_path, "B3", runs["flag"])
            primary = labels["primary"]
            mine = [r for r in primary["labels"] if r["document_id"] == over]
            if {(r["class"], r["basis"]) for r in mine} != {("ABSTAIN", "over_context_excluded")}:
                problems.append("excluded rows %s" % {(r["class"], r["basis"]) for r in mine})
            others = [r for r in primary["labels"] if r["document_id"] != over]
            if any(r["basis"] == "over_context_excluded" for r in others):
                problems.append("a fitting document was excluded")
            counts = primary["counts"]
            if (counts["over_context_excluded_documents"], counts["items_over_context_excluded"]) != (1, n_over):
                problems.append("counts %s" % counts)
            listed = primary["over_context"]
            if (listed["checked"], listed["documents"], listed["items"]) != (True, 1, n_over) or [
                    (d["document_id"], d["over_context_calls"], d["over_context_by_agent"])
                    for d in listed["excluded_documents"]] != [
                    (over, 3, {"LEGAL_ANALYST": 2, "SPEECH_ACT_TAGGER": 1})]:
                problems.append("listed %s" % listed)
            # every sensitivity keeps the exclusion except S-7, which makes it ABSTAIN
            for name in ("S-1", "S-2", "S-3", "S-5", "S-6", "S-8"):
                if {r["basis"] for r in labels[name]["labels"] if r["document_id"] == over} != {"over_context_excluded"}:
                    problems.append(name + " lost the exclusion")
            s7 = {(r["class"], r["basis"]) for r in labels["S-7"]["labels"] if r["document_id"] == over}
            if s7 != {("ABSTAIN", "s7_over_context_abstain")}:
                problems.append("S-7 %s" % s7)
            # scored: the excluded document is in no analysis but S-7
            scored = cli.score(adapter, labels, self.root / "b")
            for name, result in scored.items():
                want = (len(fits) + 1, n_all) if name == "S-7" else (len(fits), n_all - n_over)
                if name == "S-4":
                    want = (want[0], result["decisions"])     # S-4 drops its own items
                if (result["documents"], result["decisions"]) != want:
                    problems.append("%s scored %s" % (name, (result["documents"], result["decisions"])))
            if scored["S-7"]["coverage"]["answered"] != n_all - n_over:
                problems.append("S-7 answered %s" % scored["S-7"]["coverage"])
            # the paired view: B0 against B3 and B3 against B0 both drop it; B0 alone keeps all
            b0 = cli.label(adapter, items_path, "B0")
            with_b3 = cli.score(adapter, b0, self.root / "b", paired_with=labels)
            if with_b3["primary"]["documents"] != len(fits) + 1:
                problems.append("B0 alone %s" % with_b3["primary"]["documents"])
            paired = with_b3["paired"]
            if (paired["documents"], paired["left_out_over_context"]["other_arm"],
                    paired["analyses"]["primary"]["documents"], sorted(paired["analyses"])) != (
                    len(fits), [over], len(fits), ["S-1", "S-2", "S-3", "S-4", "S-5", "S-6", "S-8", "primary"]):
                problems.append("B0 paired %s" % {k: v for k, v in paired.items() if k != "analyses"})
            back = cli.score(adapter, labels, self.root / "b", paired_with=b0)["paired"]
            if (back["documents"], back["left_out_over_context"]["this_arm"],
                    back["analyses"]["primary"]["decisions"]) != (len(fits), [over], n_all - n_over):
                problems.append("B3 paired %s" % {k: v for k, v in back.items() if k != "analyses"})
            return problems

        self._proof(body, lambda: mock.patch.object(m, "OVER_CONTEXT_FIELD", "never_written"))
        self._proof(body, lambda: mock.patch.object(m, "OVER_CONTEXT_ARMS", ()))
        self._proof(body, lambda: mock.patch.object(m, "scored_view", lambda spec, result: result))
        self._proof(body, lambda: mock.patch.object(m, "over_context_excluded", lambda result: set()))
        self._proof(body, lambda: mock.patch.object(m, "sensitivity_s7", m.sensitivity_s1))

    def test_without_the_flag_b3_is_labelled_as_before(self):
        # Reply records whose context fits (or states none, or is absent) change nothing:
        # every analysis equals that of the same runs with no reply records at all, and B1,
        # B2 and B4 are never checked for it.
        c, adapter, items_path, by_doc, over, fits, runs = self._setup()
        m, cli = c["mapping"], c["cli"]

        def view(result):
            return sorted((r["item_id"], r["class"], r["basis"]) for r in result["labels"])

        def body():
            problems = []
            fit = cli.label(adapter, items_path, "B3", runs["noflag"])
            bare = cli.label(adapter, items_path, "B3", runs["bare"])
            for name in fit:
                if view(fit[name]) != view(bare[name]):
                    problems.append(name + " differs")
            if fit["primary"]["over_context"]["documents"] or fit["primary"]["counts"]["items_over_context_excluded"]:
                problems.append("excluded %s" % fit["primary"]["over_context"])
            # B4 reads the same runs and is not checked: nothing excluded, even with the flag
            b4 = cli.label(adapter, items_path, "B4", runs["flag"])
            if b4["primary"]["over_context"]["checked"] or any(
                    r["basis"] == "over_context_excluded" for r in b4["primary"]["labels"]):
                problems.append("B4 excluded")
            if cli.score(adapter, fit, self.root / "b")["primary"]["decisions"] != sum(len(v) for v in by_doc.values()):
                problems.append("fit scored on fewer items")
            return problems
        # neutralised: a reader that takes any record with a context object as over it
        loose = lambda run_dir: {"reply_records": 1, "records_with_context": 1, "over_context_calls": 1,  # noqa: E731
                                 "over_context_by_agent": {"X": 1}, "unreadable_records": 0}
        self._proof(body, lambda: mock.patch.object(m, "read_over_context", loose))
        self._proof(body, lambda: mock.patch.object(m, "OVER_CONTEXT_ARMS", ("B3", "B4")))

    def test_the_development_findver_run_is_excluded(self):
        # Counts only, on the saved L4b FinDVer B3 run where external/ holds it (skipped
        # otherwise): the three calls over their model's context the draft of section 12
        # item 14 lists (SPEECH_ACT_TAGGER, LEGAL_ANALYST, VERIFIER).
        run = EXTERNAL / "s05" / "labels" / "_runs" / "B3" / "findver" / "L4b" / "e61777d6327c"
        if not (run / "audit" / "model_replies").is_dir():
            self.skipTest("external/ does not hold the S5 development runs")
        m = _common()["mapping"]
        over = m.read_over_context(run)
        self.assertEqual((over["over_context_calls"], over["over_context_by_agent"], over["unreadable_records"]),
                         (3, {"LEGAL_ANALYST": 1, "SPEECH_ACT_TAGGER": 1, "VERIFIER": 1}, 0))
        with mock.patch.object(m, "OVER_CONTEXT_FIELD", "never_written"):
            self.assertEqual(m.read_over_context(run)["over_context_calls"], 0)


class S8Checks(_Case):
    """Sensitivity S-8 (DEV-012), on hand-written synthetic B3 runs: B3 and B4 scored as if
    every record written by a model were absent. Only records stamped `written_by` exactly
    `python` are kept (an unstamped record is a model's, section 3 item 6) and section 5.1's
    lines apply unchanged to what remains: an item a model-written record decided takes the
    next line (a Python ok record, a Python refusal), else silence; a Python-decided item,
    a run failure and an over-context exclusion are unchanged; B0, B1 and B2 equal their
    primary and say so. Neutralise, fail, restore, pass."""

    RULES = ["CONV-CNLI-NDA-%d" % k for k in range(1, 7)]

    def _proof(self, body, neutralise):
        self.assertEqual(body(), [], "shipped")
        with neutralise():
            self.assertNotEqual(body(), [], "neutralised, the proof still passed")
        self.assertEqual(body(), [], "restored")

    def _items(self, doc, rules):
        return [{"item_id": "i-%s-%d" % (doc, k), "document_id": doc, "rule_id": rule, "benchmark": "contractnli"}
                for k, rule in enumerate(rules)]

    def _runs(self):
        r = self.RULES
        python = [_rec("p1", r[1], "ok"), _rec("p2", r[2], "irregular"), _rec("p3", r[3], "ok"),
                  _rec("p5", r[5], "irregular", confidence="UNCERTAIN")]
        model = [_rec("m0", r[0], "irregular"), _rec("m1", r[1], "irregular"), _rec("m2", r[2], "ok"),
                 _rec("m4", r[4], "irregular", confidence="UNCERTAIN"), _rec("m5", r[5], "irregular")]
        root = self.root / "s8"
        _incomplete_run(root, "dmix", completion=_completion(), bus_lines=[
            _bus_line("PRACTICE_AUDITOR", "dmix", python, "paired", "python"),
            _bus_line("PRACTICE_AUDITOR", "dmix", model, _MODEL_BACKEND, _MODEL_ID, call_id="c" * 32)])
        # a run failure and an over-context exclusion stay what they are under S-8
        _incomplete_run(root, "dfail", completion=_completion("stopped", reached_end=False), bus_lines=[
            _bus_line("PRACTICE_AUDITOR", "dfail", [_rec("m9", r[0], "irregular")], _MODEL_BACKEND, _MODEL_ID)])
        over = _incomplete_run(root, "dover", completion=_completion(), bus_lines=[
            _bus_line("PRACTICE_AUDITOR", "dover", [_rec("m8", r[0], "irregular")], _MODEL_BACKEND, _MODEL_ID)])
        _reply_record(over, 1, "LEGAL_ANALYST", _ctx(36413, 32768))
        items = self._items("dmix", r) + self._items("dfail", r[:1]) + self._items("dover", r[:1])
        path = self.root / "items.json"
        path.write_text(json.dumps({"items": items}), encoding="utf-8")
        return root, path

    # primary and S-8, by item: class and basis
    PRIMARY = {"i-dmix-0": ("FLAG", "irregular"), "i-dmix-1": ("FLAG", "irregular"),
               "i-dmix-2": ("FLAG", "irregular"), "i-dmix-3": ("CLEAR", "ok"),
               "i-dmix-4": ("UNDECIDED", "refusal"), "i-dmix-5": ("FLAG", "irregular"),
               "i-dfail-0": ("ABSTAIN", "run_failure"), "i-dover-0": ("ABSTAIN", "over_context_excluded")}
    S8 = dict(PRIMARY, **{
        "i-dmix-0": ("CLEAR", "silent"),          # a model's irregular record alone: silence
        "i-dmix-1": ("CLEAR", "ok"),              # a model's irregular over Python's ok: the ok
        "i-dmix-4": ("CLEAR", "silent"),          # a model's refusal alone: silence
        "i-dmix-5": ("UNDECIDED", "refusal")})    # a model's irregular over Python's refusal

    def test_s8_drops_every_model_written_record(self):
        c = _common()
        m, cli = c["mapping"], c["cli"]
        adapter = _adapter("contractnli")
        root, path = self._runs()

        def view(result):
            return {r["item_id"]: (r["class"], r["basis"]) for r in result["labels"]}

        def body():
            problems = []
            for arm in ("B3", "B4"):
                labels = cli.label(adapter, path, arm, root)
                want, want8 = dict(self.PRIMARY), dict(self.S8)
                if arm == "B4":     # B4 is not checked for the context (section 5.3)
                    want["i-dover-0"], want8["i-dover-0"] = ("FLAG", "irregular"), ("CLEAR", "silent")
                if view(labels["primary"]) != want:
                    problems.append("%s primary %s" % (arm, view(labels["primary"])))
                s8 = labels["S-8"]
                if view(s8) != want8:
                    problems.append("%s S-8 %s" % (arm, view(s8)))
                if (s8["analysis"], s8.get("s8_applies")) != ("S-8", True):
                    problems.append("%s S-8 header %s" % (arm, (s8["analysis"], s8.get("s8_applies"))))
                # the unattached findings under S-8 are Python's alone
                stray = [d["unattached"]["count"] for d in s8["documents"] if d["document_id"] == "dmix"]
                if stray != [0]:
                    problems.append("%s S-8 unattached %s" % (arm, stray))
            return problems

        self._proof(body, lambda: mock.patch.object(m, "python_only_view", lambda run: run))
        self._proof(body, lambda: mock.patch.object(m, "S8_ARMS", ()))
        self._proof(body, lambda: mock.patch.object(m, "sensitivity_s8", lambda spec, result: dict(
            m._alternative(spec, result, "s3", "S-8", result["documents"]), s8_applies=True)))

    def test_an_unstamped_record_is_a_models(self):
        # The bus reader stamps every record it reads, so an unstamped record is held on the
        # run as the record reader hands it over: dropped under S-8, like any stamp that is
        # not exactly `python`.
        m = _common()["mapping"]
        spec = _adapter("contractnli").SPEC
        rule = self.RULES[0]
        base = {"failure": False, "pairing_refusals": [], "judging_calls": [], "rule_map": {},
                "rule_map_status": "missing", "completeness": {}}
        cases = {
            "unstamped": ([_rec("u1", rule, "irregular")], ("CLEAR", "silent")),
            "case": ([_rec("u2", rule, "irregular", written_by="Python")], ("CLEAR", "silent")),
            "unstamped_over_python_ok": ([_rec("u3", rule, "irregular"),
                                          _rec("u4", rule, "ok", written_by="python")], ("CLEAR", "ok")),
            "python": ([_rec("u5", rule, "irregular", written_by="python")], ("FLAG", "irregular"))}

        def body():
            problems = []
            for name, (recs, want) in cases.items():
                run = dict(base, records=recs)
                primary = m.classify(spec, rule, run)
                got = m.classify(spec, rule, m.python_only_view(run))
                if (primary["class"], primary["basis"]) != ("FLAG", "irregular"):
                    problems.append("%s primary %s" % (name, primary["class"]))
                if (got["class"], got["basis"]) != want:
                    problems.append("%s S-8 %s" % (name, (got["class"], got["basis"])))
            return problems

        self._proof(body, lambda: mock.patch.object(m, "is_computed", lambda r: r.get("written_by") != "model"))
        self._proof(body, lambda: mock.patch.object(m, "python_only_view", lambda run: run))

    def test_other_arms_equal_their_primary_and_say_so(self):
        # B0, B1 and B2: S-8 equals the primary, in the labels and in the score, and says so;
        # for B2 even where its review_data.json holds a record no python stamp claims.
        c = _common()
        m, cli = c["mapping"], c["cli"]
        adapter = _adapter("contractnli")
        _build("contractnli", self.root / "b")
        items_path = self.root / "b" / "items.json"
        items = m.read_items(items_path)
        runs = self.root / "b2"
        b1 = self.root / "b1"
        for doc, doc_items in m.by_document(items).items():
            folder = runs / doc / "deliverables" / doc
            folder.mkdir(parents=True)
            (runs / doc / "audit").mkdir()
            (runs / doc / "audit" / "run_completion.json").write_text(json.dumps(_completion()), encoding="utf-8")
            (folder / "review_data.json").write_text(json.dumps({"findings": [
                _rec("b1", doc_items[0]["rule_id"], "irregular")]}), encoding="utf-8")
            (b1 / doc / "labels").mkdir(parents=True)
            for item in doc_items:
                (b1 / doc / "labels" / (item["item_id"] + ".json")).write_text(
                    json.dumps({"label": "Contradiction", "evidence": ""}), encoding="utf-8")

        def body():
            problems = []
            for arm, folder in (("B0", None), ("B1", b1), ("B2", runs)):
                labels = cli.label(adapter, items_path, arm, folder)
                same = [(r["class"], r["basis"]) for r in labels["S-8"]["labels"]] == [
                    (r["class"], r["basis"]) for r in labels["primary"]["labels"]]
                if not same or labels["S-8"].get("s8_applies") is not False \
                        or labels["S-8"].get("note") != m.S8_NOTE_EQUAL:
                    problems.append(arm + " S-8 differs or does not say so")
                scored = cli.score(adapter, labels, self.root / "b")
                if scored["S-8"]["headline"] != scored["primary"]["headline"] \
                        or scored["S-8"].get("note") != m.S8_NOTE_EQUAL:
                    problems.append(arm + " S-8 score differs or does not say so")
            return problems

        self._proof(body, lambda: mock.patch.object(m, "S8_ARMS", ("B2", "B3", "B4")))


class SetupFailureChecks(_Case):
    """One setup-failure rule for B1 and B3 (D-084, DEV-014), on a synthetic ContractNLI
    build: a B1 document whose output holds b1_setup_failure.json, and a B3 document whose
    run has a reply record of a call that failed out of memory, carry basis setup_failure on
    every item, are counted apart (never abstentions), are left out of that arm's scoring in
    every analysis but S-7, which scores them ABSTAIN, and a paired comparison drops a
    document either arm failed on; a failed call of any other kind is no setup failure.
    Neutralise, fail, restore, pass."""

    def _proof(self, body, neutralise):
        self.assertEqual(body(), [], "shipped")
        with neutralise():
            self.assertNotEqual(body(), [], "neutralised, the proof still passed")
        self.assertEqual(body(), [], "restored")

    def _setup(self):
        c = _common()
        adapter = _adapter("contractnli")
        _build("contractnli", self.root / "b")
        items_path = self.root / "b" / "items.json"
        by_doc = c["mapping"].by_document(c["mapping"].read_items(items_path))
        docs = sorted(by_doc)
        self.assertGreaterEqual(len(docs), 2, "the synthetic build needs two documents")
        b1_fail, b3_fail = docs[0], docs[-1]
        b1, b3 = self.root / "b1", self.root / "b3"
        for doc in docs:
            out = b1 / doc
            (out / "labels").mkdir(parents=True)
            for k, item in enumerate(by_doc[doc]):
                if doc == b1_fail and k:      # the run stopped at its second item
                    break
                (out / "labels" / (item["item_id"] + ".json")).write_text(
                    json.dumps({"label": "Contradiction", "evidence": ""}), encoding="utf-8")
            if doc == b1_fail:
                (out / "b1_setup_failure.json").write_text(json.dumps(
                    {"schema": "b1-setup-failure-v1", "kind": "out_of_memory",
                     "item_id": by_doc[doc][min(1, len(by_doc[doc]) - 1)]["item_id"]}), encoding="utf-8")
            rules = [i["rule_id"] for i in by_doc[doc]]
            failed = doc == b3_fail
            run = _incomplete_run(b3, doc, completion=_completion("failed", reached_end=False, exit_code=1)
                                  if failed else _completion(),
                                  bus_lines=[_bus_line("A", doc, [_rec("x1", rules[0], "irregular")],
                                                       "paired", "python")])
            folder = run / "audit" / "model_replies"
            folder.mkdir(parents=True)
            # an ordinary failed call is no setup failure; only out of memory or a refused kernel is
            calls = [("RuntimeError", "VERIFIER")] + ([("out_of_memory", "PROCESSOR")] if failed else [])
            for n, (kind, agent) in enumerate(calls, 1):
                (folder / ("%06d_%032x.json" % (n, n))).write_text(json.dumps(
                    {"schema_version": 1, "sequence": n, "agent": agent, "backend_ok": False,
                     "error_category": kind}), encoding="utf-8")
        return c, adapter, items_path, by_doc, docs, b1_fail, b3_fail, b1, b3

    def test_one_setup_failure_rule_for_b1_and_b3(self):
        c, adapter, items_path, by_doc, docs, b1_fail, b3_fail, b1, b3 = self._setup()
        m, cli = c["mapping"], c["cli"]
        n_all = sum(len(v) for v in by_doc.values())

        def body():
            problems = []
            for arm, runs, failed in (("B1", b1, b1_fail), ("B3", b3, b3_fail)):
                labels = cli.label(adapter, items_path, arm, runs)
                primary = labels["primary"]
                mine = {(r["class"], r["basis"]) for r in primary["labels"] if r["document_id"] == failed}
                if mine != {("ABSTAIN", "setup_failure")}:
                    problems.append("%s failed rows %s" % (arm, mine))
                if any(r["basis"] == "setup_failure" for r in primary["labels"] if r["document_id"] != failed):
                    problems.append(arm + ": another document is a setup failure")
                counts = primary["counts"]
                n = len(by_doc[failed])
                if (counts["setup_failure_documents"], counts["items_setup_failure"]) != (1, n) \
                        or counts["abstain"] != sum(1 for r in primary["labels"] if r["label"] == "ABSTAIN"
                                                    and r["basis"] != "setup_failure"):
                    problems.append("%s counts %s" % (arm, counts))
                listed = primary["setup_failure"]
                if (listed["checked"], listed["documents"], listed["items"]) != (True, 1, n):
                    problems.append("%s listed %s" % (arm, listed))
                s7 = {(r["class"], r["basis"]) for r in labels["S-7"]["labels"] if r["document_id"] == failed}
                if s7 != {("ABSTAIN", "s7_setup_failure_abstain")}:
                    problems.append("%s S-7 %s" % (arm, s7))
                scored = cli.score(adapter, labels, self.root / "b")
                for name, result in scored.items():
                    want = (len(docs), n_all) if name == "S-7" else (len(docs) - 1, n_all - n)
                    if name == "S-4":
                        want = (want[0], result["decisions"])
                    if (result["documents"], result["decisions"]) != want:
                        problems.append("%s %s scored %s" % (arm, name, (result["documents"], result["decisions"])))
            # the paired view drops a document either arm failed on
            l1 = cli.label(adapter, items_path, "B1", b1)
            l3 = cli.label(adapter, items_path, "B3", b3)
            paired = cli.score(adapter, l3, self.root / "b", paired_with=l1)["paired"]
            gone = {b1_fail, b3_fail}
            if (paired["documents"], paired["left_out_setup_failure"]) != (
                    len(docs) - len(gone), {"this_arm": [b3_fail], "other_arm": [b1_fail]}):
                problems.append("paired %s" % {k: v for k, v in paired.items() if k != "analyses"})
            return problems

        self._proof(body, lambda: mock.patch.object(m, "read_b1_setup_failure", lambda d: None))
        self._proof(body, lambda: mock.patch.object(m, "read_b3_setup_failure", lambda d: None))
        self._proof(body, lambda: mock.patch.object(m, "SETUP_FAILURE_ARMS", ()))
        self._proof(body, lambda: mock.patch.object(m, "setup_failure_excluded", lambda result: set()))
        self._proof(body, lambda: mock.patch.object(m, "sensitivity_s7", m.sensitivity_s1))
        self._proof(body, lambda: mock.patch.object(m, "B3_SETUP_FAILURE_KINDS", ("out_of_memory", "RuntimeError")))


SYNTHETIC = ADAPTERS / "synthetic"


def _synthetic_test(root):
    """The hand-written synthetic test (benchmark/adapters/synthetic/fixtures), materialised:
    each bundle's files, and its key as answer_key.json (a tracked file named like a key would
    be ignored by git, so the key travels inside the fixture under `gold`)."""
    data = _json(SYNTHETIC / "fixtures" / "synthetic_test.json")
    for name, spec in data["bundles"].items():
        for rel, text in spec["files"].items():
            path = Path(root) / name / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        (Path(root) / name / "answer_key.json").write_text(json.dumps(spec["gold"]), encoding="utf-8")
    return Path(root)


def _syn_item_id(source):
    return hashlib.sha256(("item:synthetic:" + source).encode("utf-8")).hexdigest()[:12]


def _syn_rec(item_id, rule, verdict, unit, relation, field_label=None, a=None, b=None, **extra):
    return dict({"item_id": item_id, "source_rule_id": rule, "unit_id": unit, "relation": relation,
                 "record_verdict": verdict, "field_label": field_label, "value_a": a, "value_b": b},
                **extra)


class SyntheticChecks(_Case):
    """B's synthetic tests (preregistration section 13), on a hand-written test of three
    bundles: items are (target document, rule) pairs read from the targets file and the
    conventions, never from the key; units are Shimmer's; B0, B1, B2 and B3 are labelled
    through the shared core (every record decides the rule it names); scores count location
    by unit and relation under any rule with the attribution apart, the reason by the key's
    claim, false positives, distractor hits and the twin's false alarms, and leave a
    negotiation-style key unscored. Neutralise, fail, restore, pass."""

    def _proof(self, body, neutralise):
        self.assertEqual(body(), [], "shipped")
        with neutralise():
            self.assertNotEqual(body(), [], "neutralised, the proof still passed")
        self.assertEqual(body(), [], "restored")

    def _syn(self):
        return _adapter("synthetic")

    def _test(self):
        return _synthetic_test(self.root / "test")

    ITEMS = [("flawed_a", "log_q1", "CONV-GA"), ("flawed_a", "log_q1", "CONV-GB"),
             ("rounds_c", "log_q3", "CONV-GA"), ("twin_b", "log_q2", "CONV-GA"),
             ("twin_b", "log_q2", "CONV-GB")]

    def test_items_are_read_from_targets_and_conventions_never_the_key(self):
        syn = self._syn()
        root = self._test()
        want = sorted((_syn_item_id("%s/%s/%s" % t), t[1], t[2], t[0]) for t in self.ITEMS)

        def body():
            problems = []
            try:
                first = syn.item_rows(root)
                for name in ("flawed_a", "twin_b", "rounds_c"):    # an unreadable key changes nothing
                    (root / name / "answer_key.json").write_text("not json", encoding="utf-8")
                second = syn.item_rows(root)
            except Exception as exc:  # noqa: BLE001
                return ["raised %s" % type(exc).__name__]
            finally:
                _synthetic_test(root)
            got = sorted((r["item_id"], r["document_id"], r["rule_id"], r["bundle"]) for r in first)
            if got != want:
                problems.append("items %s" % got)
            if first != second:
                problems.append("the key changed the items")
            if {r["benchmark"] for r in first} != {"synthetic"}:
                problems.append("benchmark %s" % {r["benchmark"] for r in first})
            return problems

        def reads_key(original):
            def item_rows(root_):
                rows = original(root_)
                planted = {(n, p["rule"]) for n in ("flawed_a", "twin_b") for p in json.loads(
                    (Path(root_) / n / "answer_key.json").read_text(encoding="utf-8")).get("planted") or []}
                return [r for r in rows if r["bundle"] == "rounds_c" or (r["bundle"], r["rule_id"]) in planted]
            return item_rows
        self._proof(body, lambda: mock.patch.object(syn, "item_rows", reads_key(syn.item_rows)))
        self._proof(body, lambda: mock.patch.object(syn, "target_names", lambda f: ["context/ref_g.md"]))

    def test_units_are_shimmers(self):
        syn = self._syn()
        root = self._test()
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import pairing_map
        finally:
            sys.path.remove(str(ROOT / "scripts"))
        texts = [p.read_text(encoding="utf-8") for p in sorted(root.rglob("log_q*.md"))]
        suite = ROOT / "benchmark" / "dev_suite" / "generated"
        if suite.is_dir():      # the development suite, where it has been generated
            for keyfile in sorted(suite.rglob("answer_key.json")):
                folder = keyfile.parent
                for name in syn.target_names(folder):
                    texts.append((folder / "context" / name).read_text(encoding="utf-8").replace("\r\n", "\n"))

        def body():
            problems = []
            for text in texts:
                mine = [uid for uid, _t in syn.units(text)]
                theirs = [u["unit_id"] for u in pairing_map.split_units(text)]
                if mine != theirs:
                    problems.append("units %s against %s" % (mine[:4], theirs[:4]))
            if [uid for uid, _t in syn.units(texts[0])] != ["u00-gauge-log", "u01-entry-alpha",
                                                           "u02-entry-beta", "u03-entry-gamma"]:
                problems.append("fixture units %s" % syn.units(texts[0]))
            return problems
        self._proof(body, lambda: mock.patch.object(syn, "_slug", lambda text, limit=40: str(text).lower()))
        self._proof(body, lambda: mock.patch.object(syn, "_RULE_LINE", re.compile(r"^.*$")))

    def _runs(self, root):
        """Hand-written B2, B3 and B1 outputs, one folder per bundle."""
        docs = {"flawed_a": "log_q1", "twin_b": "log_q2", "rounds_c": "log_q3"}
        b2, b3, b1 = self.root / "b2", self.root / "b3", self.root / "b1"
        b2_findings = {
            "flawed_a": [_syn_rec("f1", "CONV-GA", "irregular", "u01-entry-alpha", "above_band", "reading", 12, 10,
                                  written_by="python"),
                         _syn_rec("f2", "CONV-GB", "irregular", "u02-entry-beta", "sum_mismatch", "total count", 7, 9,
                                  written_by="python"),
                         _syn_rec("f3", "CONV-GA", "ok", "u03-entry-gamma", "above_band", "reading", 8, 10,
                                  written_by="python")],
            "twin_b": [_syn_rec("t1", "CONV-GA", "ok", "u01-entry-alpha", "above_band", "reading", 9, 10,
                                written_by="python")],
            "rounds_c": []}
        for name, doc in docs.items():
            folder = b2 / name / "deliverables" / doc
            folder.mkdir(parents=True)
            (b2 / name / "audit").mkdir()
            (b2 / name / "audit" / "run_completion.json").write_text(json.dumps(_completion()), encoding="utf-8")
            (folder / "review_data.json").write_text(json.dumps({"findings": b2_findings[name]}), encoding="utf-8")
        python = {"flawed_a": [_syn_rec("p1", "CONV-GA", "irregular", "u01-entry-alpha", "above_band", "reading", 12, 10),
                               # under another rule than the key's, and with the wrong figures
                               _syn_rec("p2", "CONV-GA", "irregular", "u02-entry-beta", "sum_mismatch", "total count", 6, 9)],
                  "twin_b": [], "rounds_c": []}
        model = {"flawed_a": [_syn_rec("m1", "CONV-GA", "irregular", "u03-entry-gamma", "above_band", "reading", 8, 10)],
                 "twin_b": [_syn_rec("m2", "CONV-GA", "irregular", "u01-entry-alpha", "above_band", "reading", 9, 10)],
                 "rounds_c": []}
        for name, doc in docs.items():
            lines = [_bus_line("A", doc, python[name], "paired", "python")]
            if model[name]:
                lines.append(_bus_line("B", doc, model[name], _MODEL_BACKEND, _MODEL_ID, call_id="c" * 32))
            run = _incomplete_run(b3, doc, completion=_completion(), bus_lines=lines)
            run.rename(b3 / name)
        # the model's record on the clean unit is shown in one deliverable
        shown = b3 / "flawed_a" / "deliverables" / "log_q1"
        shown.mkdir(parents=True)
        (shown / "document_summary.md").write_text("Written by a model: record m1.\n", encoding="utf-8")
        replies = {("flawed_a", "CONV-GA"): {"label": "violated", "evidence": "Reading: 12 units."},
                   # held by two units: locates none
                   ("flawed_a", "CONV-GB"): {"label": "violated", "evidence": "Limit: 10 units."},
                   ("twin_b", "CONV-GA"): {"label": "holds", "evidence": ""},
                   ("twin_b", "CONV-GB"): {"label": "not a label", "evidence": ""},
                   ("rounds_c", "CONV-GA"): {"label": "holds", "evidence": ""}}
        for (name, rule), reply in replies.items():
            path = b1 / name / "labels" / (_syn_item_id("%s/%s/%s" % (name, docs[name], rule)) + ".json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(reply), encoding="utf-8")
        return {"B2": b2, "B3": b3, "B1": b1}

    LABELS = {
        "B0": {k: ("CLEAR", "b0", []) for k in ITEMS},
        "B1": {("flawed_a", "log_q1", "CONV-GA"): ("FLAG", "b1_label", ["u01-entry-alpha"]),
               ("flawed_a", "log_q1", "CONV-GB"): ("FLAG", "b1_label", []),
               ("twin_b", "log_q2", "CONV-GA"): ("CLEAR", "b1_label", []),
               ("twin_b", "log_q2", "CONV-GB"): ("ABSTAIN", "b1_parse_failure", []),
               ("rounds_c", "log_q3", "CONV-GA"): ("CLEAR", "b1_label", [])},
        "B2": {("flawed_a", "log_q1", "CONV-GA"): ("FLAG", "irregular", ["u01-entry-alpha"]),
               ("flawed_a", "log_q1", "CONV-GB"): ("FLAG", "irregular", ["u02-entry-beta"]),
               ("twin_b", "log_q2", "CONV-GA"): ("CLEAR", "ok", []),
               ("twin_b", "log_q2", "CONV-GB"): ("CLEAR", "silent", []),
               ("rounds_c", "log_q3", "CONV-GA"): ("CLEAR", "silent", [])},
        "B3": {("flawed_a", "log_q1", "CONV-GA"): ("FLAG", "irregular",
                                                  ["u01-entry-alpha", "u02-entry-beta", "u03-entry-gamma"]),
               ("flawed_a", "log_q1", "CONV-GB"): ("CLEAR", "silent", []),
               ("twin_b", "log_q2", "CONV-GA"): ("FLAG", "irregular", ["u01-entry-alpha"]),
               ("twin_b", "log_q2", "CONV-GB"): ("CLEAR", "silent", []),
               ("rounds_c", "log_q3", "CONV-GA"): ("CLEAR", "silent", [])}}
    # (planted, located, attributed, reason confirmed, item false positives, records on
    # unplanted units, distractor hits, twin false alarms: flagged items and unit-rule pairs)
    SCORES = {"B0": (2, 0, 0, 0, 0, 0, 0, (0, 0)),
              "B1": (2, 1, 1, None, 0, 0, 0, (0, 0)),
              "B2": (2, 2, 2, 2, 0, 0, 0, (0, 0)),
              "B3": (2, 2, 1, 1, 1, 2, 2, (1, 1))}
    S8 = {"B3": (2, 2, 1, 1, 0, 0, 0, (0, 0))}

    def _labelled(self, syn, root, runs, arm):
        items = self.root / "items.json"
        syn.write_items(root, items)
        return syn.label(items, arm, root, runs.get(arm))

    def _score_view(self, scored):
        t = scored["totals"]
        base = [b for b in scored["bundles"] if b["bundle"] == "flawed_a"][0]
        twin = base["twin_false_alarms"] or {}
        return (t["planted"], t["located"], t["attributed"], t["reason_confirmed"], t["item_false_positives"],
                t["records_on_unplanted_units"], t["distractor_hits"],
                (twin.get("flag_items"), twin.get("flagged_unit_rule_pairs")))

    def test_labels_and_scores_by_hand(self):
        syn = self._syn()
        root = self._test()
        runs = self._runs(root)

        def body():
            problems = []
            for arm in ("B0", "B1", "B2", "B3"):
                labels = self._labelled(syn, root, runs, arm)
                got = {(r["bundle"], r["document_id"], r["rule_id"]): (r["class"], r["basis"], r["cited_unit_ids"])
                       for r in labels["primary"]["labels"]}
                if got != self.LABELS[arm]:
                    problems.append("%s labels %s" % (arm, got))
                scored = syn.score(labels, root)
                if self._score_view(scored["primary"]) != self.SCORES[arm]:
                    problems.append("%s score %s" % (arm, self._score_view(scored["primary"])))
                if [s["bundle"] for s in scored["primary"]["not_scored"]] != ["rounds_c"]:
                    problems.append("%s not scored %s" % (arm, scored["primary"]["not_scored"]))
                want8 = self.S8.get(arm, self.SCORES[arm])
                if self._score_view(scored["S-8"]) != want8:
                    problems.append("%s S-8 %s" % (arm, self._score_view(scored["S-8"])))
                if self._score_view(scored["S-3"]) != self.SCORES[arm]:
                    problems.append("%s S-3 differs from the primary" % arm)
                # the records on unplanted units, by the deliverable that shows them
                shown = {"B1": None, "B3": {"document_summary.md": 1}}.get(arm, {})
                if scored["primary"]["totals"]["unplanted_records_per_deliverable"] != shown:
                    problems.append("%s per deliverable %s" % (
                        arm, scored["primary"]["totals"]["unplanted_records_per_deliverable"]))
                if arm == "B3" and scored["S-8"]["totals"]["unplanted_records_per_deliverable"] != {}:
                    problems.append("B3 S-8 per deliverable")
            return problems

        m = _common()["mapping"]
        # every record decides the rule it names: set aside, the sum record decides nothing
        self._proof(body, lambda: mock.patch.object(syn.SPEC, "attribute_as_named", False))
        # location by unit: neutralised, a record anywhere locates every flaw
        self._proof(body, lambda: mock.patch.object(syn, "_on_unit", lambda planted, unit: True))
        # the reason by the key's claim: neutralised, every located record confirms it
        self._proof(body, lambda: mock.patch.object(syn, "reason_matches", lambda claim, record: True))
        # B1 located only by a sentence one unit holds: neutralised, by every unit holding it
        quote = lambda e: (e or "").rstrip(".").strip()  # noqa: E731
        self._proof(body, lambda: mock.patch.object(syn, "b1_located_units", lambda e, u: (
            sorted(uid for uid, text in u if quote(e) and quote(e) in " ".join(text.split())), 0)))
        # S-8 drops the model's records
        self._proof(body, lambda: mock.patch.object(m, "python_only_view", lambda run: run))
        # a record shown in a deliverable is counted there
        self._proof(body, lambda: mock.patch.object(syn, "in_deliverables", lambda record, texts: []))

    def test_b1_prompt_for_a_synthetic_item(self):
        syn = self._syn()
        c = _common()
        root = self._test()
        items = self.root / "items.json"
        syn.write_items(root, items)
        item = [r for r in c["mapping"].read_items(items)
                if r["bundle"] == "flawed_a" and r["rule_id"] == "CONV-GA"][0]
        spec = c["prompt"].load_prompt()
        user = c["prompt"].render_user(
            spec, item["benchmark"], document=(root / "flawed_a" / "context" / "log_q1.md").read_text(encoding="utf-8"),
            conventions=c["prompt"].conventions_from_bundle(root / "flawed_a"), item=item,
            reference=c["prompt"].reference_from_bundle(root / "flawed_a"))
        self.assertIn("ITEM\nItem id: %s\nRule id: CONV-GA\nDecide whether any passage of the document "
                      "breaks this rule.\n" % item["item_id"], user)
        self.assertIn("LABELS\nviolated: at least one passage of the document breaks the rule.\n"
                      "holds: no passage of the document breaks the rule.\n"
                      "undecided: the material does not let you decide.\nThe undecided label is: undecided", user)
        self.assertIn("REFERENCE MATERIAL\nref_g.md\n# Bench reference", user)
        self.assertIn("CONVENTIONS\nCONV-GA Reading limit [required] [conformance]: The reading must not "
                      "exceed the limit.\nCONV-GB Count total", user)
        self.assertNotIn("If the material does not let you decide",
                         c["prompt"].render_system(spec, "synthetic"), "the undecided label is not invited")
        # bare_model.py reads exactly these four fields, and the document id is the target's stem
        self.assertEqual((item["document_id"], sorted(k for k in ("item_id", "document_id", "rule_id", "benchmark")
                                                      if item.get(k))),
                         ("log_q1", ["benchmark", "document_id", "item_id", "rule_id"]))
        self.assertEqual(syn.SPEC.b1_labels, {"violated": "FLAG", "holds": "CLEAR", "undecided": "UNDECIDED"})


# ---------------------------------------------------------------------------
# the dry-run document choice and free measurements (benchmark/dryrun; S5 items 0.6, 0.7)


DRYRUN = ROOT / "benchmark" / "dryrun"


def _dryrun(name):
    """A benchmark/dryrun module, loaded with sys.path restored afterwards."""
    key = "dryrun_" + name
    if key not in _MODULES:
        _common()
        before = list(sys.path)
        try:
            sys.path.insert(0, str(DRYRUN))
            sys.path.insert(0, str(ADAPTERS))
            spec = importlib.util.spec_from_file_location("benchmark_dryrun_" + name, DRYRUN / (name + ".py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path[:] = before
        _MODULES[key] = module
    return _MODULES[key]


class _GuardedRow(dict):
    """A bands row that fails when any field but words, band, side and opaque id is read."""

    def _allowed(self, key):
        if key not in ("document_id", "words", "length_band", "side"):
            raise AssertionError("the choice read " + str(key))

    def __getitem__(self, key):
        self._allowed(key)
        return dict.__getitem__(self, key)

    def get(self, key, default=None):
        self._allowed(key)
        return dict.get(self, key, default)


class DryRunChecks(_Case):
    """Item 0.6: the content-blind choice reads words, band, side and opaque id only, sorts
    by words then opaque id, takes evenly spaced positions (the median for one) and lists
    each choice's replacement. Item 0.7 and R24: the build restricted to chosen documents,
    B2 on it, the B1 prompt tokens and the memory bound, on a synthetic build with a
    stand-in counter."""

    def setUp(self):
        super().setUp()
        if not DRYRUN.is_dir():
            self.skipTest("benchmark/dryrun/ is not present here")

    def test_positions_and_choice(self):
        choose = _dryrun("choose")
        self.assertEqual(choose.positions(5, 1), [2])
        self.assertEqual(choose.positions(4, 1), [1])
        self.assertEqual(choose.positions(132, 3), [32, 65, 98])
        self.assertEqual(choose.positions(3, 3), [0, 1, 2])
        with self.assertRaises(ValueError):
            choose.positions(2, 3)
        rows = [_GuardedRow(document_id=i, words=w, length_band=b, side=s, gold="x",
                            source_document_id="src-" + i)
                for i, w, b, s in (("d5", 300, "A", "development"), ("d1", 100, "A", "development"),
                                   ("d3", 200, "A", "development"), ("d2", 200, "A", "development"),
                                   ("d4", 250, "A", "holdout"), ("d6", 1500, "B", "development"),
                                   ("d7", 1200, "B", "development"))]
        got = choose.choose("x", rows, plan={"A": 1, "B": 1}, fallback={})
        # band A development order: d1 100, d2 200, d3 200 (tie by id), d5 300: lower median d2
        self.assertEqual([(r["band"], r["document_id"], r["position"], r["band_size"]) for r in got],
                         [("A", "d2", 2, 4), ("B", "d7", 1, 2)])
        self.assertEqual([r["replacement"]["document_id"] for r in got], ["d3", "d6"])
        two = choose.choose("x", rows, plan={"A": 2}, fallback={"B": 1})
        # n = 4, k = 2: 1-based positions floor(5/3) = 1 and floor(10/3) = 3
        self.assertEqual([(r["role"], r["document_id"]) for r in two],
                         [("chosen", "d1"), ("chosen", "d3"), ("fallback", "d7")])
        self.assertEqual(two[1]["replacement"]["document_id"], "d5")
        self.assertNotIn("src-", json.dumps(got + two))
        self.assertEqual(set(choose.PLAN), set(NAMES))

    def test_memory_bound_by_hand(self):
        # D-056 condition 8, computed by hand: L 2, H 2, Hkv 1, h 4 (d 2), m 6, V 10, a 100-byte
        # file; prompt P 3, allowance 2, so T 5. Non-4-bit parameters 2*10*4 + 2*2*4 + 4 +
        # 2*(4 + 2*1*2) = 116, doubled from bf16 to float32: weights 100 + 2*116 = 332. KV cache
        # 2*2*1*2*5*4 = 160 (float32). sdpa: 2*2*2*5*4 + 2*3*4 = 184, no T x T term; eager:
        # 2*3*3*8 + 3*3*4 = 180, over the prompt only. Activations 3*(16 + 18)*4 = 408 (float32),
        # dequantized 6*4*2 = 48, logits 40.
        measure = _dryrun("measure")
        dims = {"num_hidden_layers": 2, "num_attention_heads": 2, "num_key_value_heads": 1,
                "hidden_size": 4, "intermediate_size": 6, "vocab_size": 10, "weights_file_bytes": 100}
        self.assertEqual(measure.non_4bit_parameters(dims), 116)
        self.assertEqual(measure.non_4bit_parameters(dict(dims, tie_word_embeddings=True)), 76)
        common = {"weights": 332, "kv_cache": 160, "activations": 408, "dequantized": 48, "logits": 40,
                  "runtime": 1 << 30}
        bound = measure.memory_bound(3, 2, dims)
        self.assertEqual((bound["attention"], bound["prompt_tokens"], bound["tokens"]), ("sdpa", 3, 5))
        self.assertEqual(bound["bytes"], dict(common, attention=184))
        self.assertEqual(bound["total_bytes"], 1172 + (1 << 30))
        self.assertFalse(bound["over_limit"])
        eager = measure.memory_bound(3, 2, dims, "eager")
        self.assertEqual(eager["bytes"], dict(common, attention=180))
        # eager's square is over the prompt only: the allowance moves only the KV cache and sdpa
        longer = measure.memory_bound(3, 20, dims, "eager")
        self.assertEqual(longer["bytes"]["attention"], 180)
        self.assertEqual(longer["bytes"]["kv_cache"], 2 * 2 * 1 * 2 * 23 * 4)
        with self.assertRaises(ValueError):
            measure.memory_bound(3, 2, dims, "flash")
        # Qwen2.5-7B's shape at a full-length prompt (context 32,768 less a 2,048 allowance): the
        # eager square alone is 215 GB; sdpa has none, and its bound sits just over the 22 GB
        # limit, mostly one-shot prefill's float32 activations (8.7 GB)
        big = {"num_hidden_layers": 28, "num_attention_heads": 28, "num_key_value_heads": 4, "hidden_size": 3584,
               "intermediate_size": 18944, "vocab_size": 152064, "weights_file_bytes": 5547254622}
        full = measure.memory_bound(32768 - 2048, 2048, big)
        self.assertEqual((full["total_gb"], full["bytes"]["activations"]), (22.38, 30720 * 71168 * 4))
        self.assertEqual(measure.memory_bound(32768 - 2048, 2048, big, "eager")["total_gb"], 236.61)

    def test_recompute_from_a_written_summary(self):
        measure = _dryrun("measure")
        dims = {"num_hidden_layers": 2, "num_attention_heads": 2, "num_key_value_heads": 1,
                "hidden_size": 4, "intermediate_size": 6, "vocab_size": 10, "weights_file_bytes": 100}
        summary = {"model_dimensions": dims, "output_allowance": 2, "memory_formula": "old",
                   "documents": [{"benchmark": "findver", "part_rule": None, "document_id": "d1", "role": "chosen",
                                  "band": "A", "b1_prompt_tokens": {"max": 3},
                                  "memory_bound": {"total_gb": 9.0, "over_limit": False}}]}
        path = self.root / "summary.json"
        path.write_text(json.dumps(summary), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(measure.main(["recompute", "--summary", str(path), "--out",
                                           str(self.root / "again.json")]), 0)
        row = _json(self.root / "again.json")["documents"][0]
        self.assertEqual((row["prompt_tokens"], row["tokens"], row["recorded_bound_gb"]), (3, 5, 9.0))
        self.assertEqual((sum(row["sdpa_bytes"].values()), sum(row["eager_bytes"].values())),
                         (1172 + (1 << 30), 1168 + (1 << 30)))

    def test_restricted_build_b2_and_b1_tokens(self):
        measure = _dryrun("measure")
        c = _common()
        adapter = _adapter("scitab")
        every = {d["document_id"] for d in adapter.documents(adapter.read_source(_source("scitab")),
                                                              {"development": True})}
        wanted = sorted(every)[0]
        out = self.root / "build"
        c["cli"].build(measure.Only(adapter, [wanted]), _source("scitab"), out, development=True,
                       synthetic=True, max_context=4096, output_allowance=64,
                       token_counter=measure.StandIn)
        record = _json(out / "parts.json")["documents"]
        self.assertEqual([d["document_id"] for d in record], [wanted], "only the chosen document is built")
        items = [i for i in _json(out / "items.json")["items"] if i["document_id"] == wanted]
        sys.path.insert(0, str(ROOT / "benchmark" / "baselines"))
        try:
            row = measure.measure_document("scitab", out / wanted, items, record[0], self.root / "b2",
                                           measure.StandIn, measure._stand_in_dims(), 64)
        finally:
            sys.path.remove(str(ROOT / "benchmark" / "baselines"))
        pairing = _json(self.root / "b2" / "audit" / "pairing_map.json")[wanted]
        self.assertEqual((row["units"], row["plans_not_asked"], row["b2_model_calls"]),
                         (len(pairing["units"]), pairing["ablation_not_asked_count"], 0))
        self.assertEqual(row["b1_prompt_tokens"]["items"], len(items))
        self.assertGreaterEqual(row["b1_prompt_tokens"]["max"], row["b1_prompt_tokens"]["document_tokens"])
        self.assertEqual(row["memory_bound"]["tokens"], row["b1_prompt_tokens"]["max"] + 64)
        self.assertEqual((row["memory_bound"]["attention"], row["memory_bound_eager"]["attention"]),
                         ("sdpa", "eager"))
        self.assertEqual(row["memory_bound"]["prompt_tokens"], row["b1_prompt_tokens"]["max"])
        self.assertEqual(row["words"], record[0]["source_words"])


# ---------------------------------------------------------------------------
# the B-dev development items (counts only; skipped when external/ does not hold them)


def _dev(name, *parts):
    return EXTERNAL.joinpath(name, "dev", *parts)


class DevelopmentChecks(_Case):
    """Adversarial round 2, item 12: the confirmations S4c made on the development items,
    held by a check. Counts only, never text; the items stay where B-dev put them."""

    def setUp(self):
        super().setUp()
        if not (EXTERNAL / "_bdev").is_dir():
            self.skipTest("the B-dev development items are not under external/ here")

    def _built(self, name, source, **options):
        if not source.is_file():
            self.skipTest("%s: no development file at %s" % (name, source))
        _build(name, self.root / name, source, synthetic=False, **options)
        return (_json(self.root / name / "parts.json")["documents"],
                _json(self.root / name / "items.json")["items"])

    def test_contractnli_development_counts(self):
        docs, items = self._built("contractnli", _dev("contractnli", "dev.json"))
        self.assertEqual((len(docs), len(items)), (61, 1037))
        self.assertEqual(sum(len(d["parts"]) for d in docs), 5039)
        self.assertEqual(sum(d["spans"] for d in docs), 5102)
        self.assertEqual(sum(len(d["spans_without_text"]) for d in docs), 63)
        self.assertEqual((min(len(d["parts"]) for d in docs), max(len(d["parts"]) for d in docs)), (20, 255))
        self.assertEqual({d["side"] for d in docs}, {"development"})

    def test_contradoc_groups_equal_b_dev_split(self):
        source = _dev("contradoc", "ContraDoc.development.json")
        frozen = _dev("contradoc", "contradoc_split_development.json")
        if not frozen.is_file():
            self.skipTest("no B-dev split file")
        docs, items = self._built("contradoc", source, assignment=frozen)
        self.assertEqual((len(docs), len(items)), (184, 184))
        own = {r["source_document_id"]: r["split_key"] for r in
               _adapter("contradoc").split_rows(_adapter("contradoc").read_source(source))}
        self.assertEqual({d["source_document_id"]: d["cluster"] for d in docs}, own)
        self.assertEqual(len(set(own.values())), 125)

    def test_cuad_scitab_findver_development_counts(self):
        docs, items = self._built("cuad", _dev("cuad", "CUAD_v1.development.json"))
        self.assertEqual((len(docs), len(items)), (96, 96 * 41))
        docs, items = self._built("scitab", _dev("scitab", "sci_tab.development.json"))
        self.assertEqual((len(docs), len(items), len({d["cluster"] for d in docs})), (29, 95, 15))
        docs, items = self._built("findver", _dev("findver", "data", "testmini.json"),
                                  reports=_dev("findver", "financial_reports"))
        self.assertEqual((len(docs), len(items)), (255, 700))
        self.assertTrue(all(d["issuer_cik"] for d in docs))

    # Claims round 3, items 2 and 3: the remaining figures the preregistration and
    # SELECTION.md cite from the development items, held here (counts only).

    def test_contradoc_one_part_documents_and_evidence(self):
        source = _dev("contradoc", "ContraDoc.development.json")
        frozen = _dev("contradoc", "contradoc_split_development.json")
        if not (source.is_file() and frozen.is_file()):
            self.skipTest("no ContraDoc development file or B-dev split file")
        adapter, c = _adapter("contradoc"), _common()
        docs = adapter.documents(adapter.read_source(source), {"development": True, "assignment": str(frozen)})
        flag = [d for d in docs if d["items"][0]["gold"] == "contradictory"]
        self.assertEqual((len(docs), sum(len(d["parts"]) == 1 for d in docs)), (184, 123))
        self.assertEqual((len(flag), sum(len(d["parts"]) == 1 for d in flag)), (103, 64))
        # every contradictory document's evidence sentence lies inside a single part
        self.assertTrue(all(any(c["bundle"].normalise_space(p["text"]).find(
            d["items"][0]["extra"]["evidence_sentence"]) >= 0 for p in d["parts"]) for d in flag))

    def test_contractnli_splitter_and_short_evidence_parts(self):
        source = _dev("contractnli", "dev.json")
        if not source.is_file():
            self.skipTest("no ContractNLI development file")
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import pairing_map
        finally:
            sys.path.remove(str(ROOT / "scripts"))
        adapter, c = _adapter("contractnli"), _common()
        docs = adapter.documents(adapter.read_source(source), {"frozen_for": "development"})
        agree = above = 0
        for d in docs:
            d["benchmark"] = "contractnli"
            text, record, _answers = c["bundle"].build_document("contractnli", d)
            units = [u["unit_id"] for u in pairing_map.split_units(text, document_id=d["document_id"])]
            agree += units == [p["unit_id"] for p in record["parts"]]
            above += len(record["parts"]) > 99
        self.assertEqual((len(docs), agree, above), (61, 61, 16))
        floor = c["metrics"].REVERSE_CONTAINMENT_MIN_WORDS
        words = [[c["ids"].word_count(d["parts"][k - 1]["text"]) for k in i["evidence_parts"]]
                 for d in docs for i in d["items"] if i["gold"] == "contradiction"]
        self.assertEqual(len(words), 95)
        self.assertEqual(sum(1 for w in words if any(n < floor for n in w)), 10)
        self.assertEqual(sum(1 for w in words if w and all(n < floor for n in w)), 0)

    def test_findver_table_entries_and_development_bands(self):
        source = _dev("findver", "data", "testmini.json")
        if not source.is_file():
            self.skipTest("no FinDVer development file")
        adapter, c = _adapter("findver"), _common()
        tables = with_separator = 0
        for report in sorted({r["report"] for r in adapter.read_source(source)}):
            entries, _digest, _url = adapter.read_filing(_dev("findver", "financial_reports"), report)
            for entry in entries:
                if entry.get("type") == "table":
                    tables += 1
                    with_separator += any(adapter._separator(line) for line in entry["context"].split("\n"))
        self.assertEqual((tables, with_separator), (10991, 3))
        result = c["cli"].bands(adapter, source, reports=_dev("findver", "financial_reports"))
        self.assertEqual(result["documents_by_side"], {"development": 255})
        self.assertEqual({k: v["documents"] for k, v in result["development_bands"].items()},
                         {"A": 0, "B": 4, "C": 65, "D": 186})
        self.assertEqual(sum(v["documents"] for v in result["holdout_pool_bands"].values()), 0)


class SegmentChecks(_Case):
    """D-S13 item 7 (docs/benchmarks/FINDVER_B1_REVISION.md section 3): B3 reads a long FinDVer
    filing in segments of whole parts (common/segments.py), on the synthetic filings with a
    word-count tokenizer and a small limit. The segment bundle holds the kept text exactly,
    under the document's own headings, each segment within the limit (a lone part over it
    is its own segment, listed); Shimmer's splitter gives the segment unit ids the map
    translates; the rules are the document's; no source id leaks; builds are
    byte-identical; and B3's labels read every segment's records from the one run, unit ids
    translated, a call over the context in the run excluding the whole document.
    Neutralise, fail, restore, pass."""

    LIMIT = 24
    BUDGET = {"max_context": 100000, "output_allowance": 10}

    def _build(self, out, **extra):
        return _build("findver", out, token_counter=WordCounter(overhead=50), **self.BUDGET, **extra)

    def _segmented(self, out):
        self._build(out, b3_segment_tokens=self.LIMIT)
        parts = _json(out / "parts.json")
        segmented = [d for d in parts["documents"] if d["b3_segments"]]
        self.assertTrue(segmented, "the small limit segments at least one synthetic filing")
        return parts, segmented

    def test_a_long_filing_gets_a_segment_bundle(self):
        c = _common()
        bundle, seg = c["bundle"], c["segments"]
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import pairing_map
        finally:
            sys.path.remove(str(ROOT / "scripts"))
        parts, segmented = self._segmented(self.root / "a")
        self.assertEqual(parts["b3_segment_rule"]["limit_tokens"], self.LIMIT)
        self.assertFalse(parts["b3_segment_rule"]["declared"])
        self._build(self.root / "b", b3_segment_tokens=self.LIMIT)
        self.assertEqual(_files(self.root / "a"), _files(self.root / "b"), "byte-identical builds")
        sources = {d["source_document_id"] for d in parts["documents"]}
        for record in segmented:
            doc_id = record["document_id"]
            self.assertEqual(record["b3_bundle"], "b3_segments/" + doc_id)
            folder = self.root / "a" / "b3_segments" / doc_id
            names = [s["segment_id"] + ".md" for s in record["b3_segments"]]
            self.assertEqual(sorted(p.name for p in (folder / "context").iterdir()),
                             sorted(names + ["_review_targets.json"]))
            self.assertEqual(_json(folder / "context" / "_review_targets.json")["targets"], names)
            self.assertEqual((folder / "conventions" / "rules.md").read_bytes(),
                             (self.root / "a" / doc_id / "conventions" / "rules.md").read_bytes())
            whole = {u: t for u, _h, _l, t in bundle.read_units(
                (self.root / "a" / doc_id / "context" / (doc_id + ".md")).read_text(encoding="utf-8"))}
            covered, position = [], 1
            for s in record["b3_segments"]:
                self.assertEqual(s["first"], position, "segments are consecutive")
                position = s["last"] + 1
                text = (folder / "context" / (s["segment_id"] + ".md")).read_text(encoding="utf-8")
                self.assertEqual(s["tokens"], len(text.split()))
                self.assertEqual(s["over_limit"], s["tokens"] > self.LIMIT)
                if s["over_limit"]:
                    self.assertEqual(s["first"], s["last"], "only a lone part may exceed the limit")
                mapping = seg.unit_map(s)
                units = [u["unit_id"] for u in pairing_map.split_units(text, document_id=s["segment_id"])]
                self.assertEqual(units, list(mapping), "Shimmer's splitter on a segment")
                read = bundle.read_units(text)
                self.assertEqual(len(read), len(mapping))
                for (_uid, heading, _l, body), (k, doc_uid) in zip(
                        read, zip(range(s["first"], s["last"] + 1), mapping.values())):
                    self.assertEqual(heading, "## P-%05d" % k, "the document's own heading")
                    self.assertEqual(body, whole[doc_uid], "the segment holds the kept text")
                    covered.append(doc_uid)
                for source in sources:
                    self.assertNotIn(source, text, "no source id in a segment")
            self.assertEqual(covered, [p["unit_id"] for p in record["parts"]], "every kept part once")
        # a limit every filing fits: no segment bundle, B3 reads the document's own bundle
        self._build(self.root / "c", b3_segment_tokens=100000)
        whole_parts = _json(self.root / "c" / "parts.json")
        self.assertEqual([(d["b3_bundle"], d["b3_segments"]) for d in whole_parts["documents"]],
                         [(d["document_id"], []) for d in whole_parts["documents"]])
        self.assertFalse((self.root / "c" / "b3_segments").exists())
        # the declared limit applies by default; no counter, no segments; an option alone refused
        self._build(self.root / "d")
        self.assertEqual(_json(self.root / "d" / "parts.json")["b3_segment_rule"],
                         dict(parts["b3_segment_rule"], limit_tokens=_adapter("findver").B3_SEGMENT_TOKENS,
                              declared=True))
        _build("findver", self.root / "e")
        self.assertNotIn("b3_segment_rule", _json(self.root / "e" / "parts.json"))
        with self.assertRaises(ValueError):
            _build("findver", self.root / "f", b3_segment_tokens=10)

    def test_b3_labels_a_segmented_filing_from_one_run(self):
        c = _common()
        cli, seg = c["cli"], c["segments"]
        adapter = _adapter("findver")
        parts, segmented = self._segmented(self.root / "a")
        record = segmented[0]
        doc_id = record["document_id"]
        segs = record["b3_segments"]
        items_path = self.root / "a" / "items.json"
        mine = sorted((i for i in _json(items_path)["items"] if i["document_id"] == doc_id),
                      key=lambda i: i["item_id"])
        last = segs[-1]
        unit_in_last = seg.segment_unit(1, last["first"])
        expected_unit = c["bundle"].unit_id(last["first"])
        lines = [_bus_line("PRACTICE_AUDITOR", last["segment_id"],
                           [_rec("x1", mine[0]["rule_id"], "irregular", unit=unit_in_last),
                            _rec("x9", mine[0]["rule_id"], "irregular", unit="u77-p-00999")],
                           "paired", "python")]
        if len(mine) > 1:
            lines.append(_bus_line("PRACTICE_AUDITOR", segs[0]["segment_id"],
                                   [_rec("x2", mine[1]["rule_id"], "ok", unit=seg.segment_unit(1, 1))],
                                   "paired", "python"))
        others = sorted({i["document_id"] for i in _json(items_path)["items"]} - {doc_id})
        for name in ("plain", "over"):
            root = self.root / name
            run = _incomplete_run(root, doc_id, completion=_completion(), bus_lines=lines)
            for other in others:
                _incomplete_run(root, other, completion=_completion(), bus_lines=[])
            if name == "over":
                _reply_record(run, 1, "VERIFIER", _ctx(140000, 131072))

        def body():
            problems = []
            labels = cli.label(adapter, items_path, "B3", self.root / "plain")["primary"]
            rows = {r["item_id"]: r for r in labels["labels"]}
            first = rows[mine[0]["item_id"]]
            if (first["class"], first["cited_unit_ids"]) != ("FLAG", sorted({expected_unit, "u77-p-00999"})):
                problems.append("segment record not read as the document's: %s %s"
                                % (first["class"], first["cited_unit_ids"]))
            if len(mine) > 1 and (rows[mine[1]["item_id"]]["class"], rows[mine[1]["item_id"]]["basis"]) != ("CLEAR", "ok"):
                problems.append("the first segment's ok record not read")
            doc = next(d for d in labels["documents"] if d["document_id"] == doc_id)
            if [s["segment_id"] for s in doc.get("b3_segments") or []] != [s["segment_id"] for s in segs]:
                problems.append("segments not listed")
            if not any(f.startswith(last["segment_id"] + ": segment_unit_not_in_segment") for f in doc["faults"]):
                problems.append("a unit no segment part carries is not counted: %s" % doc["faults"])
            over = cli.label(adapter, items_path, "B3", self.root / "over")["primary"]
            if {r["basis"] for r in over["labels"] if r["document_id"] == doc_id} != {"over_context_excluded"}:
                problems.append("a call over the context in a segmented run does not exclude the document")
            b2 = cli.label(adapter, items_path, "B2", self.root / "plain")["primary"]
            if any(d.get("b3_segments") for d in b2["documents"]):
                problems.append("B2 read segments")
            return problems

        self.assertEqual(body(), [], "shipped")
        with mock.patch.object(cli, "segments_beside", lambda items_path: {}):
            self.assertNotEqual(body(), [], "neutralised (no segments read), the proof still passed")
        self.assertEqual(body(), [], "restored")


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
                           "hand-counted cut line and evidence read on the kept text, an index into "
                           "a part cut mid-text not evidence; no budget, an off-side document, a "
                           "holdout document in an undeclared development build, a ContractNLI file "
                           "not frozen for its side or a testmini report is refused; empty documents "
                           "are skipped and listed; one word rule counts every part, band and cut "
                           "line (markup tokens on pipe rows not words); each release's schema is "
                           "read as the B-dev development items showed it, ContractNLI one part per "
                           "span of its own span list or merged parts under the cost fallback; the "
                           "bands command matches a build, records sides and totals the holdout "
                           "pool apart from development (a mixed-side FinDVer input with its "
                           "testmini overlap; ContraDoc refused without its frozen assignment); "
                           "demonstration documents are excluded"),
    "cli": (CliChecks, "an isolated interpreter builds FinDVer from a copied tree with every budget "
                       "option and its own --reports, keeps a table's own separator row, records "
                       "the token counter's SHA-256, refuses another adapter's option, builds SciTab "
                       "with --exclude, CUAD, and ContractNLI holdout with --frozen-sha256 and "
                       "--parts merged, and runs bands and split"),
    "development": (DevelopmentChecks, "the development counts and readings recorded from the "
                                       "B-dev items hold (skipped when external/ does not hold them)"),
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
                               "refusal, CUAD missing_field), for B2, B1 and B0 with S-1, S-2, "
                               "S-3 and S-5; a settled answer on any unit beats a refusal (S-5 "
                               "the other way), never counted in a failed run; one figure-audit definition for every benchmark "
                               "(relation and python stamp; bands decide their rule, blank-cell, "
                               "sum and product records only in a one-rule bundle, model records "
                               "always); B3 and B4 read from the bus (a run with no bus a run "
                               "failure), refused with the bus reading not adopted; the catch layer read from the "
                               "written_by stamp alone, exactly"),
    "records": (RecordReaderChecks, "one record reader for both forms: B2 from review_data.json, "
                                    "B3 from the run's bus with written_by stamped from the line, "
                                    "supersession within (agent, document, item_id) by revision, "
                                    "then ts, then line, a judged absence counted only by "
                                    "Python's stamped copy and the raw model copy listed apart, "
                                    "another document's lines ignored; the same records in both "
                                    "forms give the same labels on every mapping fixture; the "
                                    "bus reading is adopted (D-056): the label command labels B3 "
                                    "and B4 from a fixture bus as B2 from review_data.json, and "
                                    "refuses with the flag off"),
    "incomplete": (IncompleteRunChecks, "a run that reached its end with exit 0 and semantic_complete "
                                        "false is labelled from its records, S-6 makes its items ABSTAIN, "
                                        "item_calls_failed applies through the run's own registry id map "
                                        "(D-078; a missing, unreadable or many-to-one map not used, says "
                                        "why and is counted), a pairing-map refusal naming a registry id "
                                        "refuses its operator id's item, completeness is reported per "
                                        "document, and a kept D-068 answer decides its rule as a model's "
                                        "record (D-066, D-068; neutralise, fail, restore, pass)"),
    "overcontext": (OverContextChecks, "a B3 document whose run has a reply record with "
                                       "context.over_context true is excluded (listed, counted, left "
                                       "out of every analysis but S-7, which scores it ABSTAIN, and out "
                                       "of the paired view for both arms); without the flag B3 is "
                                       "labelled as with no reply records; B4 is not checked "
                                       "(section 5.3, D-078; neutralise, fail, restore, pass)"),
    "s8": (S8Checks, "S-8 (DEV-012) scores B3 and B4 as if every model-written record were "
                     "absent: an item a model's record decided takes Python's ok or refusal "
                     "record, else silence; an unstamped record or a stamp not exactly python "
                     "is dropped; a Python-decided item, a run failure and an over-context "
                     "exclusion are unchanged; B0, B1 and B2 equal their primary and say so "
                     "(neutralise, fail, restore, pass)"),
    "setupfailure": (SetupFailureChecks, "one setup-failure rule for B1 and B3 (D-084): a B1 "
                                         "document with b1_setup_failure.json and a B3 document "
                                         "with a call out of memory are ABSTAIN with basis "
                                         "setup_failure, counted apart, left out of every analysis "
                                         "but S-7 (ABSTAIN there) and out of the paired view; any "
                                         "other failed call is no setup failure (neutralise, fail, "
                                         "restore, pass)"),
    "synthetic": (SyntheticChecks, "B's synthetic tests (section 13): items from targets and "
                                   "conventions, never the key; Shimmer's units; B0, B1, B2 and "
                                   "B3 labels and scores by hand (location by unit and relation "
                                   "under any rule, attribution apart, the reason by the key's "
                                   "claim, false positives, distractor hits, the twin's false "
                                   "alarms, S-8, a negotiation-style key unscored); the B1 "
                                   "prompt for a synthetic item (neutralise, fail, restore, pass)"),
    "dryrun": (DryRunChecks, "the dry-run choice reads words, band, side and opaque id only, "
                             "sorts by words then id, takes evenly spaced positions (the median "
                             "for one) and lists each replacement; the restricted build holds only "
                             "the chosen document; B2 on it, the B1 prompt tokens and the memory "
                             "bound (computed by hand; float32 non-4-bit weights, activations and "
                             "KV cache, sdpa with no T x T term, eager squared over the prompt "
                             "only, D-056) agree, and a written summary is recomputed"),
    "metrics": (MetricChecks, "every benchmark's metric equals the hand computation on a tiny "
                              "confusion example with its headline named, and an end-to-end score "
                              "(location for B3 and B1, B1 by containment either way where parts "
                              "are marked, the reverse way for units of 5 words or more, false "
                              "positives, unlabelled gold refused, S-4) matches by hand"),
    "segments": (SegmentChecks, "B3 reads a long FinDVer filing in segments of whole parts (D-S13 "
                                "item 7): the segment bundle holds the kept text under the document's "
                                "own headings, each segment within the limit or a lone part listed over "
                                "it, Shimmer's splitter gives the mapped unit ids, the rules are the "
                                "document's, no source id leaks, builds are byte-identical; B3 labels "
                                "read every segment's records from the one run with unit ids translated, "
                                "and a call over the context excludes the whole document (neutralise, "
                                "fail, restore, pass)"),
}


def check_group(name):
    case, what = GROUPS[name]
    return _verdict([_run(case), _run(AbsentChecks)], what)


def check():
    results = [_run(case) for case, _ in GROUPS.values()] + [_run(AbsentChecks)]
    return _verdict(results, "the five benchmark adapters build byte-identical bundles that read "
                             "back as the input format and as Shimmer splits them, cut per document, "
                             "split by document with sides and frozen files enforced, leak no source "
                             "id, run from a copied tree in an isolated interpreter, map synthetic run "
                             "outputs to the expected labels (B2, B1, B0, S-1, S-2, S-3, S-5, S-6, S-7, S-8; B3 "
                             "excluded on a call over the model's context; one setup-failure rule for B1 "
                             "and B3; a long FinDVer filing read by B3 in segments and pooled back), "
                             "label and score B's synthetic tests by hand, read B2 and B3 records by one "
                             "reader with the same labels in both forms, score tiny examples as computed "
                             "by hand (S-4 included), and hold the development counts where external/ "
                             "has the development items")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--external" in argv:
        at = argv.index("--external")
        EXTERNAL = Path(argv[at + 1])
        del argv[at:at + 2]
    names = argv or list(GROUPS)
    for group in names:
        print(group, check_group(group))
    if not argv:
        print("all", check())
