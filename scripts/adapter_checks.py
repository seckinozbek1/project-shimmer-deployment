"""Gate checks for the four benchmark adapters under benchmark/adapters/ (loop stage S4c).

Every case runs on small hand-written synthetic items in each benchmark's documented
schema (the fixtures beside each adapter), in temporary folders; nothing under
config/, durable/, ontology/ or output/ is read or written, and no benchmark data under
external/ is ever needed. benchmark/ is not shipped in the container image, so with
benchmark/adapters/ absent every case is SKIPPED with the reason, never failed.

  build      building twice gives byte-identical output, and the cut rule keeps whole
             parts and writes the cut line with the hand-computed word counts
  split      the hash split rule (SHA-256 of the document's split key, mod 5) is
             recomputed here independently, and every item of a document falls on
             that document's side, including where the item's own id would not
  opaque     opaque ids equal the first 12 hex characters of SHA-256 of
             `item:<benchmark>:<source id>` (and `document:...`), and no source id
             appears in any file inside a bundle
  structure  each bundle passes a structural reading of input-format-v1-draft: the
             headings give the expected unit ids, every unit's label line is
             `Passage: part` with no digit, a source `#` line never starts a unit, one
             rule per item, the manifest names the target alone
  mapping    the section 5.1 and 5.2 mapping gives the expected label for every case
             of the hand-written run outputs (run failure, refusal, silence,
             irregular, ok, CUAD missing_field against another relation, prior
             relations), for B3, B1 and B0, with S-1 and S-2
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
NAMES = ("contradoc", "cuad", "scitab", "findver")
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
                                  for m in ("ids", "bundle", "cut", "mapping", "metrics", "cli")}
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


def _build(name, out, cut=None):
    c = _common()
    return c["cli"].build(_adapter(name), _fixture(name, "synthetic_items.json"), out,
                          *((cut[0], cut[1]) if cut else ()))


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

        def count(text):  # a stand-in tokenizer: one token per whitespace-separated word
            return len(text.split())

        # ContraDoc document 101: parts of 16, 18 and 12 words (46 in all). The rendered
        # document adds the title (2 words), and per part a heading (2) and the label
        # line (2). The cut line "[Document cut: the remaining N of M words are not
        # shown.]" is 11 words.
        _build("contradoc", self.root / "cut", (55, count))
        parts = {d["source_document_id"]: d for d in _json(self.root / "cut" / "parts.json")["documents"]}
        doc = parts[101]
        # whole: 2 + (4+16) + (4+18) + (4+12) = 60 > 55. Two whole parts with the cut line:
        # 2 + 20 + 22 + 11 = 55 <= 55; three would be 71. Removed: 46 - 34 = 12.
        self.assertEqual((doc["cut"]["cut"], doc["cut"]["parts_kept"], doc["cut"]["words_removed"],
                          doc["cut"]["words_total"]), (True, 2, 12, 46))
        text = (self.root / "cut" / doc["document_id"] / "context" / (doc["document_id"] + ".md")).read_text(encoding="utf-8")
        self.assertTrue(text.endswith("sits here.\n[Document cut: the remaining 12 of 46 words are not shown.]\n"))
        self.assertEqual([p["part"] for p in doc["parts_beyond_cut"]], [3])
        self.assertFalse(parts[409]["cut"]["cut"], "a document that fits is not cut")
        # A first part that alone does not fit is cut at the last whitespace that fits:
        # parts of 20 and 1 words, budget 15: one part with the line is 31; four words
        # and the 11-word line are 15. Removed: 21 - 4 = 17.
        first = " ".join("w%d" % i for i in range(1, 21))
        kept, info = c["cut"].cut_parts([first, "w21"], 15, count, lambda t: "\n".join(t))
        self.assertEqual(kept, ["w1 w2 w3 w4\n[Document cut: the remaining 17 of 21 words are not shown.]"])
        self.assertEqual((info["parts_kept"], info["whole_parts_kept"], info["words_removed"]), (1, 0, 17))


# ---------------------------------------------------------------------------
# split


def _independent_side(key) -> str:
    text = str(key)
    value = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest(), "big")
    return "development" if value % 5 == 0 else "holdout"


class SplitChecks(_Case):
    # the documented split key of each hash-split benchmark, read from the source record
    def _expected_keys(self, name):
        source = _json(_fixture(name, "synthetic_items.json"))
        if name == "contradoc":  # 101 and 102 share 6 of 7 sentences: one group, key 101
            return {101: "101", 102: "101", 205: "205", 409: "409"}
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
            rows = _adapter(name).split_rows(_adapter(name).read_source(_fixture(name, "synthetic_items.json")))
            for row in rows:
                self.assertEqual(row["side"], _independent_side(row["split_key"]), name)
        self.assertGreater(differs, 0, "no fixture item whose own id would fall on another side")
        self.assertIn("development", {_independent_side(k) for k in ("409", "syn-paper-bz")})

    def test_findver_official_split_drops_testmini_reports(self):
        adapter = _adapter("findver")
        records = adapter.read_source(_fixture("findver", "synthetic_items.json"))
        mini = self.root / "mini.json"
        mini.write_text(json.dumps([records[0]]), encoding="utf-8")
        args = type("A", (), {"official": "holdout", "testmini": str(mini)})()
        rows = {r["source_document_id"]: r["side"] for r in adapter.split_rows(records, args)}
        self.assertEqual(rows, {"SYN-FILING-ONE": "removed_overlap", "SYN-FILING-TWO": "holdout"})


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
                sources.update(e["title"] for e in _json(_fixture(name, "synthetic_items.json"))["data"])
            if name == "scitab":
                sources.update(r["paper_id"] for r in _json(_fixture(name, "synthetic_items.json")))
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

    def test_bundles_follow_the_input_format(self):
        for name in NAMES:
            _build(name, self.root / name)
            items = _json(self.root / name / "items.json")["items"]
            records = {d["document_id"]: d for d in _json(self.root / name / "parts.json")["documents"]}
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
        if run.get("final_status") is not None:
            (folder / "FINAL_STATUS.json").write_text(json.dumps(run["final_status"]), encoding="utf-8")
        deliverables = folder / "deliverables" / doc
        deliverables.mkdir(parents=True)
        if run.get("review_data") is not None:
            (deliverables / "review_data.json").write_text(json.dumps(run["review_data"]), encoding="utf-8")
        for file_name, text in (run.get("deliverables") or {}).items():
            (deliverables / file_name).write_text(text, encoding="utf-8")
        if run.get("pairing_map") is not None:
            (folder / "audit").mkdir()
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
            arms = {"B3": c["cli"].label(adapter, items, "B3", runs),
                    "B1": c["cli"].label(adapter, items, "B1", b1)}
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
            code = c["cli"].main(_adapter("findver"), ["label", "--items", str(items), "--arm", "B3",
                                                       "--runs", str(runs), "--out", str(self.root / "l.json")])
        self.assertEqual(code, 3)


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
        # Mean over categories (2/3 + 1/4) / 2 = 11/24.
        ab, pr = "absent", "present"
        pairs = [(ab, ab), (pr, ab), (pr, pr), (pr, pr), (A, pr), (ab, pr)]
        rows = [{"item_id": str(i)} for i in range(6)]
        answers = {str(i): {"category_row": "cuad-01" if i < 3 else "cuad-02"} for i in range(6)}
        h = _adapter("cuad").headline(pairs, rows, answers)
        self.assertAlmostEqual(h["macro_f1"], 15 / 28)
        self.assertAlmostEqual(h["present"]["precision"], 2 / 3)
        self.assertAlmostEqual(h["present"]["recall"], 0.5)
        self.assertAlmostEqual(h["secondary_mean_category_macro_f1"], 11 / 24)
        self.assertEqual(h["secondary_zero_denominators"], 2)
        # Zero division: no item predicted or gold absent -> every absent ratio is 0, three
        # zero denominators; macro (1 + 0) / 2.
        h = _adapter("cuad").headline([(pr, pr)], [{"item_id": "z"}], {"z": {"category_row": "cuad-01"}})
        self.assertAlmostEqual(h["macro_f1"], 0.5)
        self.assertEqual(h["zero_denominators"], 3)
        # FinDVer. accuracy 2/4 (ABSTAIN wrong), coverage 3/4, accuracy on answered 2/3;
        # FDV-IE 1/2, FDV-MATH 1/2 with coverage 1/2.
        e, f = "entailed", "refuted"
        pairs = [(f, f), (e, f), (A, e), (e, e)]
        answers = {str(i): {"subset": "FDV-IE" if i < 2 else "FDV-MATH"} for i in range(4)}
        h = _adapter("findver").headline(pairs, [{"item_id": str(i)} for i in range(4)], answers)
        self.assertAlmostEqual(h["accuracy"]["accuracy"], 0.5)
        self.assertAlmostEqual(h["coverage"]["coverage"], 0.75)
        self.assertAlmostEqual(h["coverage"]["accuracy_on_answered"], 2 / 3)
        self.assertAlmostEqual(h["per_subset"]["FDV-MATH"]["accuracy"]["accuracy"], 0.5)
        self.assertAlmostEqual(h["per_subset"]["FDV-MATH"]["coverage"]["coverage"], 0.5)

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
                  "labels": [row(101, "FLAG", ["u03-p-00003"]), row(102, "FLAG", ["u01-p-00001"]),
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
    "build": (BuildChecks, "two builds of every adapter are byte-identical; the cut rule keeps "
                           "whole parts and writes the hand-counted cut line"),
    "split": (SplitChecks, "the split key is the documented document key, its SHA-256 mod 5 "
                           "recomputed independently, every item of a document on its side, "
                           "FinDVer's testmini reports dropped from the holdout"),
    "opaque": (OpaqueChecks, "opaque ids are SHA-256 prefixes of the documented strings and no "
                             "source id appears in any bundle file"),
    "structure": (StructureChecks, "every bundle reads back as the input format: expected unit "
                                   "ids, `Passage: part` with no digit, escaped # lines, one "
                                   "rule per item, the target-only manifest"),
    "mapping": (MappingChecks, "the section 5.1 and 5.2 mapping gives the hand-written expected "
                               "label for every run-output case, for B3, B1 and B0, with S-1 and S-2"),
    "metrics": (MetricChecks, "every benchmark's metric equals the hand computation on a tiny "
                              "confusion example, and an end-to-end score matches by hand"),
}


def check_group(name):
    case, what = GROUPS[name]
    return _verdict([_run(case), _run(AbsentChecks)], what)


def check():
    results = [_run(case) for case, _ in GROUPS.values()] + [_run(AbsentChecks)]
    return _verdict(results, "the four benchmark adapters build byte-identical bundles that read "
                             "back as the input format, split by document, leak no source id, "
                             "map hand-written run outputs to the expected labels (B3, B1, B0, "
                             "S-1, S-2) and score tiny examples as computed by hand")


if __name__ == "__main__":
    names = sys.argv[1:] or list(GROUPS)
    for group in names:
        print(group, check_group(group))
    if not sys.argv[1:]:
        print("all", check())
