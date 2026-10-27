"""Gate check: the synthetic test generators under benchmark/generators/ (S3 items 8 to 10).

The development suite MEASURES Shimmer and is never fitted to it (D-042): every key states
the ground truth the generator planted, and no case here asserts that a key equals what
Shimmer computes. How far Shimmer agrees with the keys is a measurement, printed by
`report_agreement` (`py -3.12 scripts/generator_checks.py --agreement`), never a pass
condition.

For every generator family (and the long-range layout of the provisions family) a test
is generated from a fixed seed into a temporary folder and read back from disk, and:

- its self-validation passes on the written files: at least ten planted flaws of at
  least three kinds, each with a complete typed reason; a clean distractor; a clean
  twin that plants nothing; all four perturbation probes, probe 3 carrying a keyed flaw;
  every planted figure recomputed by the package's own code from the rendered text,
  the comparisons Python would make by the figure audit and the flaws Python does not
  compute (unit mismatches, rate, ratio and copy errors, neighbour-only carries,
  long-range windows and bands) by the ground-truth scanners, each found exactly as keyed
  and nowhere else, in every bundle (the reworded-labels probe and the reordered
  sections, carry scanner on, included);
- family 2's rate and ratio rules and family 6's carry rule as written, read a second
  time from the rendered text by independent string handling, break exactly where the
  key says (and on no clean unit), and a broken rate result on a clean unit is caught;
- every keyed rule's text, read from the written conventions, still states what its
  keyed kinds break (each family's RULE_STATEMENTS), and each validator message in
  VALIDATOR_MUTATIONS fires on its mutation (`--mutations` prints them);
- a seed whose own draw cannot make a valid test is retried with a derived sub-seed,
  deterministically, and the key records the attempt; the fixed seeds record none;
- the same seed gives byte-identical files, also in a separate process (started with
  -B, so it writes no __pycache__ into the repository) under a different string-hash
  seed;
- a planted flaw removed from the key is caught (audit kinds and ground-truth kinds), as
  is a twin left with its flaws (every family), a digit in a text value, and a missing
  probe;
- family 4's rename probes state the ground truth: a renamed term (value kept, moved by
  2.05 to 45 percent in every bundle, the twin included, or moved to another section)
  is expected not withdrawn, with the refusal kind its figures support; a withdrawal
  beside an unrelated newcomer in the same measure is expected withdrawn; every family 4
  bundle holds only case documents in context/ and carries the multi-round key
  (entries scoped by round and document, every round keyed), a dropped earlier-round
  entry caught;
- the long-range layout holds in every bundle, probes included: true distances of at
  least twelve units, the definitions not all first, cross-reference lines on some uses
  only; a positional, two label-only and a track-and-term baseline score below 1 in
  every bundle of the fixed test and of the long-range corpus's seeds (`--baselines`
  prints them and their range);
- the slug and unit id rule matches the published examples; no generator source file
  name matches a credential or key ignore pattern;
- family 4, two and three rounds: every bundle's case manifest is accepted by the
  controller's own validate_live_case_manifest (its published rules) on the documents
  the bound pipeline's _load_corpus loads, and by the generator's restatement of those
  rules, and both refuse every mutation in MUTATIONS and accept every harmless one;
- each of those parts is neutralised in process (NEUTRALISATIONS), caught on an
  unvalidated build, restored, and passes again (`--neutralisations` prints each step).

The generators are not shipped in the container image, so when benchmark/generators/
is absent every case is skipped with the reason, never failed. Every case writes only
inside temporary folders. The controller is imported read-only by the case-manifest
case; the generators themselves never import Shimmer.
"""
import copy
import fnmatch
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "benchmark" / "generators"
FIXED = [("f1", 17, {}), ("f2", 17, {}), ("f3", 17, {}), ("f4", 17, {}), ("f5", 17, {}),
         ("f6", 17, {}), ("f5", 17, {"long_range": True}), ("f4", 17, {"rounds": 3})]
_PKG = "shimmer_synthetic_generators"


def _load():
    if _PKG in sys.modules:
        return sys.modules[_PKG]
    spec = importlib.util.spec_from_file_location(_PKG, GEN / "__init__.py",
                                                  submodule_search_locations=[str(GEN)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_PKG] = mod
    spec.loader.exec_module(mod)
    return mod


def _tree_bytes(root):
    out = {}
    for dirpath, _, names in os.walk(root):
        for n in names:
            full = os.path.join(dirpath, n)
            with open(full, "rb") as fh:
                out[os.path.relpath(full, root).replace(os.sep, "/")] = fh.read()
    return out


def _digest(files):
    h = hashlib.sha256()
    for k in sorted(files):
        h.update(k.encode("utf-8") + b"\0" + files[k] + b"\0")
    return h.hexdigest()


def _key(files):
    return json.loads(files["answer_key.json"])


def _twin_errors(errs, twin):
    return [e for e in errs if e.startswith(twin) and ("unintended comparison" in e
                                                       or "ground-truth flaws differ" in e
                                                       or "band findings differ" in e)]


class GeneratorChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (GEN / "__init__.py").is_file():
            raise unittest.SkipTest("benchmark/generators/ is absent (for example inside the "
                                    "container image)")
        cls.g = _load()
        cls.tmp = tempfile.mkdtemp(prefix="gen_checks_")
        cls.written = {}
        for fam, seed, opts in FIXED:
            test = cls.g.generate(fam, seed, **opts)
            out = os.path.join(cls.tmp, "a", "%s_%s_%s" % (fam, seed, _tag(opts)))
            cls.g.bundle.write_test(test, out)
            cls.written[(fam, _tag(opts))] = out

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _read(self, fam, **opts):
        return self.g.bundle.read_test(self.written[(fam, _tag(opts))])

    def _roles(self, test):
        return self.g.bundle._roles(test)

    def test_every_family_validates_from_disk(self):
        for fam, _, opts in FIXED:
            test = self._read(fam, **opts)
            errs = self.g.bundle.validate_test(test)
            self.assertEqual(errs, [], "%s %s: %s" % (fam, opts, errs[:5]))
            roles = self._roles(test)
            key = _key(test[roles["base"]])
            flaws = key.get("planted") or key.get("band_irregularities")
            self.assertGreaterEqual(len(flaws), 10)
            self.assertGreaterEqual(len({f["kind"] for f in flaws}), 3)
            self.assertGreaterEqual(len(key["clean"]), 1)
            self.assertEqual(sorted(roles), sorted(["base", "twin"] + list(self.g.bundle.PROBES)))
            if opts.get("long_range"):
                self.assertTrue(all(e.get("related_unit") and e["distance"] >= 12 for e in key["planted"]))

    def test_every_planted_kind_the_decisions_name_is_planted(self):
        """D-042 decisions 3, 4 and 5: unit mismatches (both kinds of measure source) in
        family 1, rate, ratio and cross-unit copy errors in family 2, neighbour-only
        carries in family 6, and long-range flaws judged only from a distant unit; each
        found by the ground-truth scanners, which the audit does not model. Named by the
        scanner each needs; every kind those scanners find is planted."""
        want = {("f1", ""): {"measure"}, ("f2", ""): {"rate", "ratio", "copy"}, ("f6", ""): {"carry"},
                ("f5", "long_range-True"): {"far_window", "far_fee"}}
        for (fam, tag), checks in want.items():
            test = self.g.bundle.read_test(self.written[(fam, tag or "plain")])
            key = _key(test[self._roles(test)["base"]])
            planted = key["planted"]
            declared = [c for c in key["ground_truth_checks"] if c["check"] in checks]
            self.assertEqual({c["check"] for c in declared}, checks, fam)
            self.assertLessEqual(self.g.ground_truth.kinds(declared), {e["kind"] for e in planted}, fam)
            if fam == "f1":
                self.assertEqual({e["compared_with"] for e in planted if e["kind"] == "unit_mismatch"},
                                 {"reference", "column"})
            if fam == "f6":
                for e in planted:
                    if e["kind"] == "carry_mismatch":
                        self.assertEqual(int(e["unit"][1:3]) - int(e["depends_on_unit"][1:3]), 1)

    def test_same_seed_gives_identical_bytes(self):
        for fam, seed, opts in FIXED:
            out = os.path.join(self.tmp, "b", "%s_%s_%s" % (fam, seed, _tag(opts)))
            self.g.bundle.write_test(self.g.generate(fam, seed, **opts), out)
            first = _tree_bytes(self.written[(fam, _tag(opts))])
            self.assertEqual(_tree_bytes(out), first, "%s %s" % (fam, opts))
        here = _digest({"%s/%s" % (k, p): t.encode("utf-8")
                        for k, (f, s, o) in enumerate(FIXED)
                        for p, t in _flatten(self.g.generate(f, s, **o)).items()})
        code = ("import sys, json, hashlib, importlib.util\n"
                "sys.path.insert(0, %r)\n"
                "import generator_checks as c\n"
                "g = c._load()\n"
                "print(c._digest({'%%s/%%s' %% (k, p): t.encode('utf-8') for k, (f, s, o) in "
                "enumerate(c.FIXED) for p, t in c._flatten(g.generate(f, s, **o)).items()}))\n"
                % str(Path(__file__).resolve().parent))
        env = dict(os.environ, PYTHONHASHSEED="12345")
        # -B: the child writes no __pycache__ into the repository either.
        proc = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True,
                              env=env, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        self.assertEqual(proc.stdout.strip(), here)

    def test_removed_planted_flaw_is_caught(self):
        """An audit-computed entry and, where the family has one, a ground-truth entry,
        each removed from the key, are caught."""
        for fam, _, opts in FIXED:
            test = self._read(fam, **opts)
            base = self._roles(test)["base"]
            key = _key(test[base])
            if "planted" not in key:
                k2 = dict(key, band_irregularities=key["band_irregularities"][1:])
                t2 = dict(test, **{base: dict(test[base], **{"answer_key.json": json.dumps(k2)})})
                errs = self.g.bundle.validate_test(t2)
                self.assertTrue(any("band findings differ" in e for e in errs), "%s: %s" % (fam, errs[:3]))
                continue
            truth = self.g.ground_truth.kinds(key["ground_truth_checks"])
            for pick, msg in ((lambda e: e["kind"] not in truth, "unintended comparison"),
                              (lambda e: e["kind"] in truth, "ground-truth flaws differ")):
                drop = [e for e in key["planted"] if pick(e)][:1]
                if not drop:
                    continue
                k2 = dict(key, planted=[e for e in key["planted"] if e is not drop[0]])
                t2 = dict(test, **{base: dict(test[base], **{"answer_key.json": json.dumps(k2)})})
                errs = self.g.bundle.validate_test(t2)
                self.assertTrue(any(e.startswith(base) and msg in e for e in errs),
                                "%s %s: %s" % (fam, msg, errs[:3]))

    def test_twin_left_with_its_flaws_is_caught(self):
        for fam, _, opts in FIXED:
            test = self._read(fam, **opts)
            roles = self._roles(test)
            base, twin = test[roles["base"]], test[roles["twin"]]
            bdoc, tdoc = _key(base)["document"], _key(twin)["document"]
            twin["context/" + tdoc] = base["context/" + bdoc]
            errs = self.g.bundle.validate_test(test)
            self.assertTrue(_twin_errors(errs, roles["twin"]), "%s %s: %s" % (fam, opts, errs[:3]))

    def test_digit_in_a_text_value_is_refused(self):
        test = self._read("f2")
        base = self._roles(test)["base"]
        doc = "context/" + _key(test[base])["document"]
        lines = test[base][doc].split("\n")
        for i, ln in enumerate(lines):
            if ": " in ln and not any(ch.isdigit() for ch in ln):
                lines[i] = ln + " 7"
                break
        test[base][doc] = "\n".join(lines)
        errs = self.g.bundle.validate_test(test)
        self.assertTrue(any("a digit in a value" in e for e in errs), errs[:3])

    def test_missing_probe_is_caught(self):
        test = self._read("f4")
        del test[self._roles(test)["value_in_different_format"]]
        errs = self.g.bundle.validate_test(test)
        self.assertTrue(errs and "missing" in errs[0], errs[:2])

    def test_unit_id_rule_matches_the_published_examples(self):
        tr = self.g.bundle.tr
        self.assertEqual(tr.unit_id(2, "Item P-101"), "u02-item-p-101")
        self.assertEqual(tr.unit_id(1, "Item (A)"), "u01-item-a")
        self.assertEqual(tr.slug("!!!"), "unit")
        self.assertEqual(len(tr.slug("x" * 60)), 40)
        self.assertEqual(tr.norm("Line totals"), "line total")
        self.assertEqual(tr.norm("Item ID"), "item")
        self.assertEqual(tr.norm("Days for reply"), "day reply")
        self.assertEqual(tr.norm("series"), "sery")

    def test_settled_readings_of_the_format(self):
        """D-025: the audit reads sentences, dates and attribution as the format says
        (neutral fixture words, D-042 decision 8)."""
        au, tr = self.g.bundle.au, self.g.bundle.tr
        text = ("# T\n\nGauge note: standard\nGauge span: 48 hours\n\n"
                "The standard gauge span is 48 hours. Then a mark follows!\n| a | b |\n")
        self.assertEqual(au.reader_sentences(text),
                         ["Gauge note: standard Gauge span: 48 hours",
                          "The standard gauge span is 48 hours.", "Then a mark follows!"])
        self.assertEqual(len(tr.numbers_with_measures("Logged: 2026-03-01")), 3)
        rules = [{"id": "A", "named": ["line total"]}, {"id": "B", "named": ["line total sum"]}]
        self.assertEqual(au._attribute(rules, "line total", "sum of 3 values under line"),
                         ("B", None))
        # The audit states facts about a vanished label and never decides it (D-042).
        conv = ("# C\n\nThese rules govern the parts.\n\n"
                "## CONV-XA Other [required] [conformance]\n\n"
                "The other gauge must lie between 1 kg and 9 kg.\n\n"
                "## CONV-XB New [required] [conformance]\n\n"
                "The new mark must lie between 50 kg and 200 kg.\n")
        prior = "# T\n\n## Part Alpha\n\nOld mark: 100 kg\nOther gauge: 5 kg\n"
        target = "# T\n\n## Part Alpha\n\nNew mark: 140 kg\nOther gauge: 5 kg\n"
        res = au.audit(target, "t.md", conv, "c.md", {"p.md": prior}, "p.md")
        self.assertEqual(res["errors"], [])
        records, refusals, vanished = au.prior_records(res)
        self.assertEqual(refusals, [])
        self.assertEqual([(v["field_label"], v["newcomers_same_measure"]) for v in vanished],
                         [("old mark", ["new mark"])])
        self.assertEqual([r["relation"] for r in records], ["unchanged_from_prior"])

    def test_rename_probes_state_the_ground_truth(self):
        """D-042 decision 2: expectations from what was planted, never from Shimmer."""
        rk = self.g.bundle.RENAMED
        for test in self._f4_tests():
            for folder, files in sorted(test.items()):
                key = _key(files)
                rows = {r["kind"]: r for r in key["rename_probes"]}
                self.assertEqual(sorted(rows), sorted(self.g.bundle.RENAME_PROBE_KINDS), folder)
                for k in rk:
                    self.assertEqual(rows[k]["expect"], "not_withdrawn", folder)
                    self.assertEqual(rows[k]["false_positive_if"], "absent_since_prior", folder)
                for k in ("withdrawn", "withdrawn_beside_newcomer"):
                    self.assertEqual(rows[k]["expect"], "absent_since_prior", folder)
                self.assertNotEqual(rows["renamed_moved_to_other_section"]["unit_id"],
                                    rows["renamed_moved_to_other_section"]["prior_unit_id"])
                self.assertEqual(sorted(r["field_label"] for r in key["expected_refusals"]),
                                 sorted(rows[k]["field_label"] for k in rk))
                withdrawn = {r["field_label"] for r in key["prior_records"]
                             if r["relation"] == "absent_since_prior"}
                self.assertEqual(withdrawn, {rows["withdrawn"]["field_label"],
                                             rows["withdrawn_beside_newcomer"]["field_label"]})
                # In every bundle, the twin included: a moved rename moves by 2.05 to 45
                # percent (never within 2% of the larger figure), and the expected refusal
                # kind is the one the planted figures support.
                ft = self.g.family_terms
                for k in ("renamed_value_moved", "renamed_moved_to_other_section"):
                    r = rows[k]
                    self.assertTrue(ft.in_move_range(r["value_before"], r["value_after"]), (folder, r))
                    self.assertTrue(2.05 <= r["moved_percent"] <= 45, (folder, r))
                self.assertEqual(rows["renamed_value_unchanged"]["refusal_kind"], "possible_rename", folder)
                self.assertEqual(rows["renamed_value_moved"]["refusal_kind"], "possible_successor", folder)
                self.assertIsNone(rows["renamed_moved_to_other_section"]["refusal_kind"], folder)
                # null: Python is expected to refuse nothing; only a matched rename satisfies.
                self.assertEqual(rows["renamed_moved_to_other_section"]["satisfied_by"], ["matched_rename"])
                for k in ("renamed_value_unchanged", "renamed_value_moved"):
                    self.assertEqual(rows[k]["satisfied_by"], ["refusal", "matched_rename"], folder)
                # every expected refusal carries the figures a matched rename compares
                for r in key["expected_refusals"]:
                    row = [x for x in key["rename_probes"] if x["field_label"] == r["field_label"]][0]
                    self.assertEqual((r["value_a"], r["value_b"], r["unit"]),
                                     (row["value_after"], row["value_before"], row["unit"]), folder)
                self.assertIn("task_given_to_the_pipeline", key)
                self.assertNotIn("task", key)

    def test_rate_and_ratio_rules_as_written(self):
        """Family 2: an independent second reading of CONV-DE (a rate applied to the
        stated total) and CONV-DG (a share of the stated total), straight from the
        rendered text, finds exactly the keyed rate and ratio errors in every bundle;
        a rate result broken on a clean unit is then caught by the validator."""
        fd = self.g.family_declaration
        test = self._read("f2")
        for folder, files in sorted(test.items()):
            key = _key(files)
            text = files[_target_name(files)]
            heads = {u["id"]: u["heading"] for u in self.g.audit.parse_document(text, "t")["units"]}
            rate, ratio = fd.summaries_breaking_rules(text)
            self.assertEqual(rate, {heads[e["unit"]] for e in key["planted"] if e["kind"] == "rate_mismatch"},
                             folder)
            self.assertEqual(ratio, {heads[e["unit"]] for e in key["planted"] if e["kind"] == "ratio_mismatch"},
                             folder)
        base = self._roles(test)["base"]
        path = _target_name(test[base])
        blocks = test[base][path].split("\n## ")
        planted = {e["unit"] for e in _key(test[base])["planted"]}
        for i, b in enumerate(blocks[1:], start=1):
            uid = self.g.textrules.unit_id(i, b.split("\n", 1)[0])
            line = [ln for ln in b.split("\n") if ln.startswith(fd.RATE_RESULT_LABEL + ": ")]
            if line and uid not in planted:
                value = line[0].split(": ", 1)[1]
                blocks[i] = b.replace(line[0], "%s: %s" % (fd.RATE_RESULT_LABEL,
                                                           "1" + value), 1)
                break
        t2 = copy.deepcopy(test)
        t2[base][path] = "\n## ".join(blocks)
        errs = self.g.bundle.validate_test(t2)
        self.assertTrue(any(e.startswith(base) and "ground-truth flaws differ" in e for e in errs), errs[:3])

    def test_stock_count_rule_as_written(self):
        """Family 6: an independent second reading of CONV-LA as written ("the opening row
        must carry the sum of the quantity column of the count before it"), by plain string
        handling of the rendered text, finds exactly the units keyed under CONV-LA in every
        bundle of the fixed test and of the development suite's seeds, and no clean unit."""
        fl = self.g.family_ledger
        seeds = json.loads((ROOT / "benchmark" / "dev_suite" / "SEEDS.json").read_text(encoding="utf-8"))
        tests = [self._read("f6")] + [self.g.generate("f6", int(e["seed"])) for e in seeds["tests"]
                                      if e["family"] == "f6"]
        for test in tests:
            for folder, files in sorted(test.items()):
                key = _key(files)
                text = files[_target_name(files)]
                heads = {u["id"]: u["heading"] for u in self.g.audit.parse_document(text, "t")["units"]}
                ch = key.get("probe_change") or {}
                label = ch["label_to"] if key.get("probe") == "reworded_labels" else "Closing quantity"
                got = fl.units_breaking_carry_rule(text, label)
                self.assertEqual(got, {heads[e["unit"]] for e in key["planted"] if e["rule"] == "CONV-LA"},
                                 folder)
                self.assertFalse(got & {heads[c] for c in key["clean"]}, folder)

    def test_validator_messages_fire_on_their_mutations(self):
        """Each validator message in VALIDATOR_MUTATIONS is produced by its mutation of a
        valid written test (the four the adversarial round named, and a keyed rule's text
        reverted to what its flaw does not break)."""
        ok, detail = observe_validator_mutations(self.g, self._read)
        self.assertTrue(ok, detail)

    def test_a_seed_that_cannot_build_is_retried_deterministically(self):
        """A seed whose own draw cannot make a valid test is retried inside the build with
        a derived sub-seed; the retry sequence depends only on the seed (two builds give
        identical bytes), the key records the attempt kept, and a seed that builds at its
        own draw records none."""
        for fam, seed, opts in RETRIED:
            with self.assertRaises((ValueError, self.g.bundle.ValidationError)):
                self.g.bundle.generate(self.g.build_spec(fam, seed, **opts))
            a, b = self.g.generate(fam, seed, **opts), self.g.generate(fam, seed, **opts)
            self.assertEqual(_flatten(a), _flatten(b), (fam, seed))
            self.assertEqual(self.g.bundle.validate_test(a), [])
            self.assertGreaterEqual(_key(a[sorted(a)[0]])["generator"].get("attempt", 0), 1, (fam, seed))
        for fam, _, opts in FIXED:
            test = self._read(fam, **opts)
            self.assertNotIn("attempt", _key(test[sorted(test)[0]])["generator"], (fam, opts))

    def test_long_range_baselines_score_below_one(self):
        """D-042 decision 5, revised: the related units vary in position and type, so a
        positional baseline (the first 4 units, the first k), two label-only baselines
        (the nearest, or the first, unit carrying the deciding label) and a track-and-term
        baseline (the nearest unit stating the use's term on the use's track, S3 checker
        round 3) each score below 1 in every bundle of the fixed test and of the
        long-range corpus's seeds."""
        tests = [self._read("f5", long_range=True)] + long_range_corpus(self.g)
        for test in tests:
            for folder, files in sorted(test.items()):
                if not _key(files)["planted"]:
                    continue
                scores = self.g.bundle.long_range_baselines(files)
                self.assertTrue(self.g.family_provisions.baselines_below_one(scores), (folder, scores))

    def test_multi_round_keys_in_the_round_form(self):
        """Family 4: the key carries the multi-round form of INPUT_FORMAT section 9:
        planted and clean entries scoped by round_id and document_id, the target round's
        entries the band breaches, earlier rounds keyed too; a dropped earlier-round entry
        is caught."""
        for test in self._f4_tests():
            for folder, files in sorted(test.items()):
                key = _key(files)
                case = json.loads(files[self.g.bundle.mc.FILE])
                docs = {r["round_id"]: r["document_ids"][0] for r in case["rounds"]}
                mr = key["multi_round"]
                for e in mr["planted"] + mr["clean"]:
                    self.assertEqual(docs[e["round_id"]], e["document_id"], folder)
                last = sorted(case["rounds"], key=lambda r: r["sequence"])[-1]["round_id"]
                self.assertEqual(len([e for e in mr["planted"] if e["round_id"] == last]),
                                 len(key["band_irregularities"]), folder)
            base = self._roles(test)["base"]
            key = _key(test[base])
            early = [e for e in key["multi_round"]["planted"] if e["kind"] == self.g.bundle.EARLIER_ROUND_KIND]
            self.assertTrue(early, "no earlier-round breach keyed")
            key["multi_round"]["planted"].remove(early[0])
            t2 = copy.deepcopy(test)
            t2[base]["answer_key.json"] = json.dumps(key)
            errs = self.g.bundle.validate_test(t2)
            self.assertTrue(any(e.startswith(base) and "multi-round planted entries differ" in e for e in errs),
                            errs[:3])

    def test_multi_round_bundles_hold_only_case_documents(self):
        for test in self._f4_tests():
            for folder, files in sorted(test.items()):
                case = json.loads(files[self.g.bundle.mc.FILE])
                docs = {d for r in case["rounds"] for d in r["document_ids"]}
                ctx = {p[len("context/"):].rsplit(".", 1)[0] for p in files
                       if p.startswith("context/") and not p.endswith("_review_targets.json")}
                self.assertEqual(ctx, docs, folder)
            test = self._f4_tests()[0]
            folder = sorted(test)[0]
            test[folder]["context/note_zz.md"] = "# Note\n\nA note that no round names.\n"
            man = json.loads(test[folder]["context/_review_targets.json"])
            man["grounding"] = sorted(man["grounding"] + ["note_zz.md"])
            test[folder]["context/_review_targets.json"] = json.dumps(man)
            errs = self.g.bundle.validate_test(test)
            self.assertTrue(any("files no round names" in e for e in errs), errs[:3])

    def test_long_range_holds_in_every_bundle(self):
        """D-042 decision 5, revised: true distances of at least twelve units in every
        bundle, probes included, the definitions not all first, cross-reference lines on
        some uses only; each property broken once is caught."""
        test = self._read("f5", long_range=True)
        for folder, files in sorted(test.items()):
            key = _key(files)
            self.assertFalse(key["long_range"]["definitions_first"], folder)
            self.assertTrue(all(e["distance"] >= 12 for e in key["planted"]), folder)
            self.assertEqual({e["cross_reference_line"] for e in key["planted"]} or {True, False},
                             {True, False}, folder)
        reorder = self._roles(test)["reordered_sections"]
        for mutate, msg in ((_wrong_distance, "units from"), (_every_use_crossref, "cross reference"),
                            (_figure_in_grounding, "states a figure"),
                            (_definitions_first_claimed, "definitions_first")):
            t2 = copy.deepcopy(test)
            mutate(t2[reorder])
            errs = self.g.bundle.validate_test(t2)
            self.assertTrue(any(e.startswith(reorder) and msg in e for e in errs), (msg, errs[:3]))

    def test_no_source_name_matches_a_trap_pattern(self):
        traps = ("*key*", "*config*.py", "*secret*", "*credential*")
        for dirpath, dirs, names in os.walk(GEN):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for n in names:
                self.assertFalse(any(fnmatch.fnmatch(n.lower(), t) for t in traps), n)

    # ---- family 4 as a declared multi-round case (S3 item 6, after S2) ----------------

    def _f4_tests(self):
        return [self._read("f4"), self._read("f4", rounds=3)]

    def test_case_manifests_agree_with_the_controller(self):
        """Every family 4 bundle's case manifest, read from disk, is accepted by the
        controller's validate_live_case_manifest on the documents the bound pipeline's own
        _load_corpus loads, and by the generator's restatement of its rules; every mutation
        in MUTATIONS is refused by both, every harmless one accepted by both."""
        ok, detail = observe_case_agreement(self.g, self._f4_tests())
        self.assertTrue(ok, detail)

    def test_neutralised_generator_parts_are_caught(self):
        """Neutralise, fail, restore, pass for each part, each on an unvalidated build
        (bundle.build_bundles), so the controller or the generator's own validator is what
        catches it."""
        for name, observe, build, patch_target, replacement in NEUTRALISATIONS:
            obj, attr = _resolve(self.g, patch_target)
            original = getattr(obj, attr)
            ok, detail = observe(self.g, [_unvalidated(self.g, *build)])
            self.assertTrue(ok, "%s before: %s" % (name, detail))
            setattr(obj, attr, replacement(original))
            try:
                ok, detail = observe(self.g, [_unvalidated(self.g, *build)])
            finally:
                setattr(obj, attr, original)
            self.assertFalse(ok, "%s: the neutralised part was not caught" % name)
            ok, detail = observe(self.g, [_unvalidated(self.g, *build)])
            self.assertTrue(ok, "%s restored: %s" % (name, detail))


# ---- helpers ----------------------------------------------------------------------

def _target_name(files):
    return "context/" + json.loads(files["context/_review_targets.json"])["targets"][0]


def _wrong_distance(files):
    key = _key(files)
    key["planted"][0]["distance"] += 1
    files["answer_key.json"] = json.dumps(key)


def _definitions_first_claimed(files):
    key = _key(files)
    key["long_range"]["definitions_first"] = not key["long_range"]["definitions_first"]
    files["answer_key.json"] = json.dumps(key)


def _every_use_crossref(files):
    """Give every use a cross-reference line (the baseline would then be perfect). The
    labels are the family's own (family_provisions.USE_LABEL and XREF_LABEL); the line
    names the document's first unit heading."""
    fp = _load().family_provisions
    path = _target_name(files)
    blocks = files[path].split("\n\n## ")
    first = blocks[1].split("\n", 1)[0]
    fixed = [blocks[0]]
    for b in blocks[1:]:
        if fp.USE_LABEL + ": " in b and "|" not in b and fp.XREF_LABEL + ": " not in b:
            b = (b.rstrip("\n") + "\n%s: %s" % (fp.XREF_LABEL, first)
                 + ("\n" if b.endswith("\n") else ""))
        fixed.append(b)
    files[path] = "\n\n## ".join(fixed)


def _figure_in_grounding(files):
    man = json.loads(files["context/_review_targets.json"])
    ref = [g for g in man["grounding"] if g not in man["prior"]][0]
    files["context/" + ref] = files["context/" + ref] + "\nThe standard gauge span is 30 days.\n"


# Seeds whose own draw cannot make a valid test (found by a seed sweep): family 4's
# reordered sections that leave the prior's order, family 6's carry mismatch that would
# make a row negative.
RETRIED = [("f4", 4003, {}), ("f6", 6097, {})]


def _set_key(files, key):
    files["answer_key.json"] = json.dumps(key)


def _all_related_definitions(files):
    """Every planted entry's related unit becomes the same definition unit."""
    g = _load()
    key = _key(files)
    doc = g.audit.parse_document(files[_target_name(files)], "t")
    first_def = [u["id"] for u in doc["units"] if any(ln["norm"] == "defined term" for ln in u["lines"])][0]
    for e in key["planted"]:
        e["related_unit"] = first_def
    _set_key(files, key)


def _deciders_in_plain_words(files):
    """The deciding units written in other words name their track plainly again: the
    value-free track-and-term match then finds every related unit."""
    fp = _load().family_provisions
    path = _target_name(files)
    text = files[path]
    for track, procedure in fp.PROCEDURE.items():
        text = text.replace("\nProcedure: %s\n" % procedure, "\nTrack: %s\n" % track)
    files[path] = text


def _target_round_kinds_swapped(files):
    """Two band rows of different kinds trade kinds: the target round's multi-round
    entries keep theirs."""
    key = _key(files)
    rows = key["band_irregularities"]
    a = rows[0]
    b = [r for r in rows if r["kind"] != a["kind"]][0]
    a["kind"], b["kind"] = b["kind"], a["kind"]
    _set_key(files, key)


def _clean_entry_in_another_document(files):
    """A multi-round clean entry names the document of another round."""
    key = _key(files)
    docs = sorted({e["document_id"] for e in key["multi_round"]["planted"] + key["multi_round"]["clean"]})
    c = key["multi_round"]["clean"][0]
    c["document_id"] = [d for d in docs if d != c["document_id"]][0]
    _set_key(files, key)


def _rule_text_replaced(rule, old, new):
    def mutate(files):
        conv = [p for p in files if p.startswith("conventions/")][0]
        if old not in files[conv]:
            raise AssertionError("%s: %r is not in the conventions" % (rule, old))
        files[conv] = files[conv].replace(old, new, 1)
    return mutate


# (validator message, family, options, role mutated, mutation)
VALIDATOR_MUTATIONS = [
    ("the related units are all definitions, or none is", "f5", {"long_range": True}, "base",
     _all_related_definitions),
    ("a baseline that reads no value finds every related unit", "f5", {"long_range": True}, "base",
     _deciders_in_plain_words),
    ("the target round's multi-round entries are not the band breaches", "f4", {}, "base",
     _target_round_kinds_swapped),
    ("multi-round clean entry", "f4", {"rounds": 3}, "base", _clean_entry_in_another_document),
    ("rule CONV-DE no longer states what rate_mismatch keys", "f2", {}, "base",
     _rule_text_replaced("CONV-DE", "the duty rate applied to the consignment's stated total, whether or "
                                    "not that total adds up", "the duty rate applied to the summed line values")),
    ("rule CONV-LA no longer states what carry_mismatch keys", "f6", {}, "base",
     _rule_text_replaced("CONV-LA", "carry the sum of the quantity column of the count before it",
                         "carry the closing quantity of the count before it")),
]


def observe_validator_mutations(g, read=None):
    """Each mutation applied to a valid test (read from disk by `read`, else generated):
    the valid test gives no error, and the mutated one gives its message on the mutated
    bundle."""
    lines = []
    for msg, fam, opts, role, mutate in VALIDATOR_MUTATIONS:
        test = read(fam, **opts) if read else g.generate(fam, 17, **opts)
        if g.bundle.validate_test(test):
            return False, "%s %s: the unmutated test is not valid" % (fam, opts)
        folder = g.bundle._roles(test)[role]
        t2 = copy.deepcopy(test)
        mutate(t2[folder])
        errs = g.bundle.validate_test(t2)
        hit = [e for e in errs if e.startswith(folder) and msg in e]
        if not hit:
            return False, "%s %s: %r not produced; errors %s" % (fam, opts, msg, errs[:3])
        lines.append("%s %s %s: %s" % (fam, opts, role, hit[0][:260]))
    return True, "\n".join(lines)


def long_range_corpus(g):
    """The long-range corpus's tests, generated in memory from its committed seeds."""
    seeds = json.loads((ROOT / "benchmark" / "long_range" / "SEEDS.json").read_text(encoding="utf-8"))
    return [g.generate(e["family"], int(e["seed"]), long_range=True) for e in seeds["tests"]]


def _controller():
    _shimmer_path()
    import ordinary_final_run
    return ordinary_final_run


def _shimmer_path():
    for sub in ("scripts", "tools"):
        p = str(ROOT / sub)
        if p not in sys.path:
            sys.path.insert(0, p)


def _context_members(files):
    return {p[len("context/"):]: t.encode("utf-8") for p, t in files.items() if p.startswith("context/")}


def _controller_refuses(ofr, case, members, pipeline_source):
    try:
        ofr.validate_live_case_manifest(case, ofr.case_corpus_documents(members, pipeline_source))
    except RuntimeError:
        return True
    return False


def _first_round_doc(case):
    return sorted(case["rounds"], key=lambda r: r["sequence"])[0]["document_ids"][0]


def _mutate(case, members, name):
    """One mutation of a valid case (and its documents); returns (case, members)."""
    c, m = copy.deepcopy(case), dict(members)
    s0 = c["sources"][0]
    if name == "fixture_true":
        c["fixture"] = True
    elif name == "extra_field":
        c["notes"] = "an extra field"
    elif name == "schema_two":
        c["schema_version"] = 2
    elif name == "one_round":
        keep = sorted(c["rounds"], key=lambda r: r["sequence"])[-1]
        c["rounds"] = [keep]
        c["sources"] = [s for s in c["sources"] if s["round_id"] == keep["round_id"]]
    elif name == "span_shifted":
        s0["char_start"] += 1
        s0["char_end"] += 1
    elif name == "quote_changed":
        s0["quote"] = s0["quote"][:-1] + ("x" if s0["quote"][-1] != "x" else "y")
    elif name == "round_document_absent":
        gone = _first_round_doc(c)
        m = {k: v for k, v in m.items() if k.rsplit(".", 1)[0] != gone}
    elif name == "document_in_two_rounds":
        rs = sorted(c["rounds"], key=lambda r: r["sequence"])
        rs[1]["document_ids"] = rs[1]["document_ids"] + rs[0]["document_ids"]
    elif name == "unit_id_not_an_identifier":
        s0["unit_id"] = "u01 part"
    elif name == "unknown_state":
        s0["state"] = "agreed"
    elif name == "empty_span":
        s0["char_end"] = s0["char_start"]
    elif name == "boolean_offset":
        s0["char_start"] = False
    elif name == "unknown_issue":
        s0["issue_id"] = "issue-not-declared"
    elif name == "source_in_another_round":
        other = [r for r in c["rounds"] if r["round_id"] != s0["round_id"]][0]
        s0["round_id"] = other["round_id"]
    elif name == "duplicate_sequence":
        c["rounds"][1]["sequence"] = c["rounds"][0]["sequence"]
    elif name == "no_actors":
        c["actors"] = []
    elif name == "recommendation_not_permitted":
        c["decision_support_mode"] = "recommendation"
    elif name == "case_id_with_a_space":
        c["case_id"] = "a case"
    elif name == "context_file_renamed":
        gone = _first_round_doc(c)
        m = {(k.replace(gone, gone + "x") if k.rsplit(".", 1)[0] == gone else k): v for k, v in m.items()}
    elif name == "harmless_second_actor":
        c["actors"].append({"actor_id": "observer"})
    elif name == "harmless_no_recommendation_field":
        del c["allow_recommendations"]
    elif name == "harmless_sources_reversed":
        c["sources"] = list(reversed(c["sources"]))
    else:
        raise ValueError(name)
    return c, m


MUTATIONS = ("fixture_true", "extra_field", "schema_two", "one_round", "span_shifted",
             "quote_changed", "round_document_absent", "document_in_two_rounds",
             "unit_id_not_an_identifier", "unknown_state", "empty_span", "boolean_offset",
             "unknown_issue", "source_in_another_round", "duplicate_sequence", "no_actors",
             "recommendation_not_permitted", "case_id_with_a_space", "context_file_renamed")
HARMLESS = ("harmless_second_actor", "harmless_no_recommendation_field", "harmless_sources_reversed")


def observe_case_agreement(g, tests):
    ofr = _controller()
    source = (ROOT / "scripts" / "pipeline.py").read_bytes()
    mc = g.bundle.mc
    n = 0
    for test in tests:
        for folder, files in sorted(test.items()):
            case = json.loads(files[mc.FILE])
            members = _context_members(files)
            gen_errs = mc.validate(case, mc.documents_as_loaded(
                {k: v.decode("utf-8") for k, v in members.items()}))
            if gen_errs or _controller_refuses(ofr, case, members, source):
                return False, "%s: generator %s, controller refuses %s" % (
                    folder, gen_errs[:2], _controller_refuses(ofr, case, members, source))
            n += 1
        base = test[sorted(test)[0]]
        case, members = json.loads(base[mc.FILE]), _context_members(base)
        for name in MUTATIONS + HARMLESS:
            c, m = _mutate(case, members, name)
            gen = bool(mc.validate(c, mc.documents_as_loaded({k: v.decode("utf-8") for k, v in m.items()})))
            ctrl = _controller_refuses(ofr, c, m, source)
            want = name not in HARMLESS
            if gen != want or ctrl != want:
                return False, "%s: generator refuses %s, controller refuses %s" % (name, gen, ctrl)
    return True, "%d bundles accepted by both; %d mutations refused and %d accepted by both" % (
        n, len(MUTATIONS), len(HARMLESS))


def observe_self_validation(g, tests):
    for test in tests:
        errs = g.bundle.validate_test(test)
        if errs:
            return False, "; ".join(errs[:3])
    return True, "%d tests valid" % len(tests)


def _unvalidated(g, family="f4", seed=17, opts=None):
    """A test built but not self-validated (three rounds by default for family 4)."""
    if opts is None:
        opts = {"rounds": 3} if family == "f4" else {}
    return g.bundle.build_bundles(g.build_spec(family, seed, **opts))


def _resolve(g, dotted):
    obj = g
    parts = dotted.split(".")
    for p in parts[:-1]:
        obj = getattr(obj, p)
    return obj, parts[-1]


def _shift_spans(build):
    def shifted(*args, **kwargs):
        case = build(*args, **kwargs)
        for s in case["sources"]:
            s["char_start"] += 1
            s["char_end"] += 1
        return case
    return shifted


def _scanner_off(name):
    return lambda scanners: dict(scanners, **{name: lambda res, chk: []})


def _plain_reorder(_original):
    def reorder(n, rng, planted, *rest):
        return _load().wordlists.reorder(n, rng)
    return reorder


def _block_reorder(_original):
    """Family 6 reordered by moving two blocks (wordlists.reorder) instead of a rotation:
    two new neighbour pairs then break the chain."""
    def rotate(n, rng, keep=()):
        return _load().wordlists.reorder(n, rng, keep)
    return rotate


def _no_earlier_rounds(build):
    def keyed(spec, rounds, alias=None):
        out = build(spec, rounds, alias)
        last = rounds[-1][0]
        return {"planted": [e for e in out["planted"] if e["round_id"] == last], "clean": out["clean"]}
    return keyed


# (name, observation, build arguments, generator attribute neutralised, replacement factory)
NEUTRALISATIONS = [
    ("the generator's case-manifest validator accepts anything", observe_case_agreement, ("f4",),
     "multi_round_case.validate", lambda orig: (lambda *a, **k: [])),
    ("the case spans are one character off", observe_case_agreement, ("f4",),
     "multi_round_case.build", _shift_spans),
    ("the unit-mismatch scanner finds nothing", observe_self_validation, ("f1",),
     "ground_truth.SCANNERS", _scanner_off("measure")),
    ("the rate scanner finds nothing", observe_self_validation, ("f2",),
     "ground_truth.SCANNERS", _scanner_off("rate")),
    ("the ratio scanner finds nothing", observe_self_validation, ("f2",),
     "ground_truth.SCANNERS", _scanner_off("ratio")),
    ("the cross-unit copy scanner finds nothing", observe_self_validation, ("f2",),
     "ground_truth.SCANNERS", _scanner_off("copy")),
    ("the neighbour-only carry scanner finds nothing", observe_self_validation, ("f6",),
     "ground_truth.SCANNERS", _scanner_off("carry")),
    ("the stock-count reordering breaks the chain", observe_self_validation, ("f6",),
     "wordlists.rotate", _block_reorder),
    ("the long-range window scanner finds nothing", observe_self_validation, ("f5", 17, {"long_range": True}),
     "ground_truth.SCANNERS", _scanner_off("far_window")),
    ("the long-range band scanner finds nothing", observe_self_validation, ("f5", 17, {"long_range": True}),
     "ground_truth.SCANNERS", _scanner_off("far_fee")),
    ("the long-range reordering ignores the distances", observe_self_validation, ("f5", 17, {"long_range": True}),
     "family_provisions._far_reorder", _plain_reorder),
    ("the multi-round key leaves out the earlier rounds", observe_self_validation, ("f4",),
     "bundle.multi_round_key", _no_earlier_rounds),
    ("the audit reads no label new in the later version", observe_self_validation, ("f4",),
     "audit.new_labels", lambda orig: (lambda res: {})),
]


def _tag(opts):
    return "_".join("%s-%s" % kv for kv in sorted(opts.items())) or "plain"


def _flatten(test):
    return {"%s/%s" % (folder, path): text for folder, files in test.items()
            for path, text in files.items()}


# ---- a reported measurement, never a pass condition (D-042) -----------------------

def shimmer_rename_outcomes(target_text, prior_text):
    """{earlier label: outcome} from Shimmer's own prior index, lookup and absent_checks,
    called unit by unit as the pipeline's prior comparison calls them (every paragraph
    given a REF id): `absent` for a withdrawal minted, else the refusal's reason_kind."""
    _shimmer_path()
    import paired_review as pr
    import pairing_map as pm
    import reference_tables as rt
    known = set(rt.document_unit_tokens(target_text)) | set(rt.document_unit_tokens(prior_text))
    index = pr.prior_index(prior_text, lambda i: "REF-%04d" % i, known_units=known)
    units = pm.split_units(target_text)
    present = set()
    for u in units:
        present |= pm.unit_fields(u.get("text", ""))
    out = {}
    for u in units:
        scalars, _, _ = pr.extract_fields(u.get("text", ""), known_units=known)
        slug = u["unit_id"].split("-", 1)[1] if "-" in u["unit_id"] else ""
        hits, _ = pr.prior_lookup(index, scalars, slug)
        checks, refused = pr.absent_checks(index, present, slug, scalars=scalars, hits=hits)
        for c in checks:
            out[c["stated_field"]] = "absent"
        for r in refused:
            out[r["label"]] = r.get("reason_kind") or "refused"
    return out


def _bundle_texts(files):
    man = json.loads(files["context/_review_targets.json"])
    return files["context/" + man["targets"][0]], files["context/" + man["prior"][0]]


def _python_findings(files):
    """Shimmer's Python review of the target document (multi_round_rounds.review_document:
    sums, products, blank cells, rule-stated bands, declared absences; NOT reference-table
    bands, date windows or change records), as (unit, relation, field label, figures)."""
    _shimmer_path()
    import convention_parser
    import multi_round_rounds
    with tempfile.TemporaryDirectory(prefix="gen_agree_") as td:
        conv = Path(td) / "input" / "conventions"
        conv.mkdir(parents=True)
        for p, t in files.items():
            if p.startswith("conventions/"):
                (conv / p.split("/", 1)[1]).write_text(t, encoding="utf-8", newline="\n")
        registry = convention_parser.parse_conventions(Path(td)).as_dict()
    target = _target_name(files)
    rules = [r for r in registry.get("conventions", []) if isinstance(r, dict)]
    _, found, _ = multi_round_rounds.review_document(
        {"id": "doc", "text": files[target]}, rules, {}, round_id="r1")
    return [f for f in found if str(f.get("record_verdict", "")).lower() == "irregular"]


def _same(f, unit, relation, label, a, b):
    try:
        figs = sorted([round(float(f["value_a"]), 6), round(float(f["value_b"]), 6)])
    except (KeyError, TypeError, ValueError):
        return False
    return (f.get("unit_id") == unit and f.get("relation") == relation
            and (f.get("field_label") or "") == (label or "")
            and figs == sorted([round(float(a), 6), round(float(b), 6)]))


def report_agreement(tests=None):
    """How far Shimmer's own Python agrees with the generated keys: counts, printed.

    Family 4: per rename-probe kind, what Shimmer's absent_checks does with the earlier
    label against what the key expects (ground truth). Every family: per planted kind,
    how many keyed flaws Shimmer's Python review of the document confirms. Never gating."""
    g = _load()
    if tests is None:
        tests = [g.generate(f, s, **o) for f, s, o in FIXED]
    rows = []
    for test in tests:
        roles = g.bundle._roles(test)
        base = test[roles["base"]]
        key = _key(base)
        fam = key["generator"]["family"]
        if "rename_probes" in key:
            got = shimmer_rename_outcomes(*_bundle_texts(base))
            for r in key["rename_probes"]:
                if r["kind"] not in g.bundle.RENAMED and not r["kind"].startswith("withdrawn"):
                    continue
                outcome = got.get(r["field_label"], "nothing")
                if r["expect"] == "absent_since_prior":
                    verdict = "agrees" if outcome == "absent" else "miss (%s)" % outcome
                else:
                    verdict = ("false withdrawal" if outcome == "absent"
                               else "agrees (%s)" % outcome)
                rows.append((fam, "rename probe " + r["kind"], verdict))
            found = _python_findings(base)
            for b in key["band_irregularities"]:
                hit = any(_same(f, b["unit_id"], b["relation"], b["field_label"], b["value_a"], b["value_b"])
                          for f in found)
                rows.append((fam, b["kind"], "confirmed" if hit else "not confirmed"))
            continue
        found = _python_findings(base)
        for e in key["planted"]:
            c = e["claim"]
            hit = any(_same(f, e["unit"], e["relation"], c["field_label"], c["value_a"], c["value_b"])
                      for f in found)
            rows.append((fam, e["kind"], "confirmed" if hit else "not confirmed"))
    counts = {}
    for fam, kind, verdict in rows:
        counts[(fam, kind, verdict)] = counts.get((fam, kind, verdict), 0) + 1
    lines = ["%-5s %-34s %-28s %d" % (f, k, v, n) for (f, k, v), n in sorted(counts.items())]
    return "\n".join(["Shimmer's Python against the generated keys (a measurement, never a gate).",
                      "Planted flaws: Shimmer's Python review of the document "
                      "(multi_round_rounds.review_document), which computes no reference-table band, "
                      "no date window and no change record, so those kinds read 'not confirmed' by "
                      "the path's scope. Rename probes: paired_review.absent_checks on the two "
                      "versions, against the key's ground truth."] + lines)


def report_baselines():
    """The long-range baselines per test and bundle (fixed seed and corpus seeds): the
    share of planted entries whose related unit a baseline that reads no value finds."""
    g = _load()
    tests = [g.generate("f5", 17, long_range=True)] + long_range_corpus(g)
    lines = ["Long-range baselines (1 would be perfect; every bundle must stay below 1)."]
    ranges = {}
    for test in tests:
        roles = g.bundle._roles(test)
        for role in ["base"] + list(g.bundle.PROBES):
            files = test[roles[role]]
            s = g.bundle.long_range_baselines(files)
            lines.append("%-28s %-28s k=%d first_4=%.3f first_k=%.3f label_nearest=%.3f label_first=%.3f "
                         "track_term=%.3f"
                         % (roles[role], role, s["k"], s["first_4"], s["first_k"], s["label_nearest"],
                            s["label_first"], s["track_term"]))
            for b in g.family_provisions.BASELINES:
                ranges.setdefault(b, []).append(s[b])
    lines.append("Range over these bundles: " + ", ".join(
        "%s %.3f to %.3f" % (b, min(v), max(v)) for b, v in ranges.items()))
    return "\n".join(lines)


def probe_open_item_22():
    """OPEN_ITEMS item 22, reproducible: the pairing map's band_conditions record
    (reference_tables.band_conditions_for_unit) calls the low side conditional where the
    finding path (paired_review.compute_checks) treats it as firm, on the shape of the
    input format's own unit-price example in neutral words (a gauge rate of 5 zed/box
    against the band 8 to 15 for its part group). Returns (map record, finding's
    conditional_on)."""
    _shimmer_path()
    import paired_review as pr
    import pairing_map as pm
    import reference_tables as rt
    unit = "## Part P-100\n\nPart group: Alpha\nCount: 4 box\nGauge rate: 5 zed/box\nPart sum: 20 zed\n"
    table = "| Part group | Rate band (zed/box) |\n|---|---|\n| Alpha | 8 to 15 |\n| Beta | 3 to 6 |\n"
    rule = "The gauge rate must lie within the rate band for the part group."
    known = rt.document_unit_tokens(unit)
    tables = rt.parse_tables(table, ref_id="REF-0002", document_id="ref", known_units=known)
    labels = pm.unit_fields(unit)
    record = rt.band_conditions_for_unit(tables, unit, [{"id": "CONV-001", "rule": rule}], vocabulary=labels)
    scalars, columns, _ = pr.extract_fields(unit, known_units=known)
    checks = pr.compute_checks(scalars, columns, rule_text=rule,
                               reference_bands=rt.bands_for_unit(tables, unit, rule),
                               vocabulary=labels, unit_labels=labels, unit_text=unit)
    below = [c for c in checks if c["relation"] == "below_band" and c.get("stated_field") == "gauge rate"]
    return ([(r["low_side_verdict"], r["condition_fields"]) for r in record],
            [c.get("conditional_on") for c in below])


def check():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GeneratorChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        first = (result.failures + result.errors)[0]
        return ("FAIL", "%d failures, %d errors; first: %s %s"
                % (len(result.failures), len(result.errors), first[0].id().rsplit(".", 1)[-1],
                   first[1].strip().splitlines()[-1][:300]))
    if result.skipped:
        return ("SKIP", "generator checks skipped: %s" % result.skipped[0][1])
    return ("PASS", "%d cases: six generator families and the long-range layout each generate "
                    "a test from a fixed seed that validates from disk (ten or more typed "
                    "flaws of three or more kinds, a distractor, a flawless twin, four probes, "
                    "probe 3 on a keyed flaw, every figure recomputed by the package's own audit "
                    "and ground-truth scanners with nothing unkeyed, in every bundle); unit "
                    "mismatches, rate, ratio and copy errors, neighbour-only carries and "
                    "long-range flaws are planted; family 2's rate and ratio rules and family 6's "
                    "carry rule as written break exactly where keyed; every keyed rule's text "
                    "states what it keys and %d validator messages fire on their mutations; a "
                    "seed that cannot build is retried deterministically; the same seed gives "
                    "identical bytes, also in a second process; a removed planted flaw (audit and "
                    "ground-truth kinds), a flawed twin in every family, a digit in a text value and "
                    "a missing probe are caught; family 4's rename probes state the ground truth "
                    "(moves of 2.05 to 45 percent in every bundle), its bundles hold only case "
                    "documents and carry the multi-round key; the long-range layout holds in every "
                    "bundle and its positional, label-only and track-and-term baselines score below "
                    "1; ids follow the published slug rule; no source name matches a trap pattern; "
                    "family 4's case manifests are accepted by the controller and the generator "
                    "alike, %d mutations refused by both; %d neutralisations caught and restored. No "
                    "case compares a key with Shimmer's output (D-042)"
                    % (result.testsRun, len(VALIDATOR_MUTATIONS), len(MUTATIONS), len(NEUTRALISATIONS)))


def report_neutralisations():
    """Each neutralisation in NEUTRALISATIONS, printed step by step: before (passes),
    neutralised (must fail), restored (passes again), with each observation's detail.
    The same steps test_neutralised_generator_parts_are_caught asserts."""
    g = _load()
    lines, caught = [], 0
    for name, observe, build, patch_target, replacement in NEUTRALISATIONS:
        obj, attr = _resolve(g, patch_target)
        original = getattr(obj, attr)
        before = observe(g, [_unvalidated(g, *build)])
        setattr(obj, attr, replacement(original))
        try:
            during = observe(g, [_unvalidated(g, *build)])
        finally:
            setattr(obj, attr, original)
        after = observe(g, [_unvalidated(g, *build)])
        ok = before[0] and not during[0] and after[0]
        caught += ok
        lines.append("%s %s (%s)" % ("CAUGHT" if ok else "NOT CAUGHT", name, patch_target))
        lines.append("  before:      %s %s" % ("pass" if before[0] else "FAIL", before[1][:300]))
        lines.append("  neutralised: %s %s" % ("pass" if during[0] else "FAIL", during[1][:300]))
        lines.append("  restored:    %s %s" % ("pass" if after[0] else "FAIL", after[1][:300]))
    lines.append("%d of %d neutralisations caught and restored" % (caught, len(NEUTRALISATIONS)))
    return "\n".join(lines)


if __name__ == "__main__":
    if "--agreement" in sys.argv:
        print(report_agreement())
    elif "--probe-open-item-22" in sys.argv:
        print(probe_open_item_22())
    elif "--neutralisations" in sys.argv:
        print(report_neutralisations())
    elif "--baselines" in sys.argv:
        print(report_baselines())
    elif "--mutations" in sys.argv:
        print(observe_validator_mutations(_load())[1])
    else:
        unittest.main()
