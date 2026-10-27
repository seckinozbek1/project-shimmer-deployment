"""Gate check: the synthetic test generators under benchmark/generators/ (S3 items 8 to 10).

For every generator family (and the long-range layout of the provisions family) a test
is generated from a fixed seed into a temporary folder and read back from disk, and:

- its self-validation passes on the written files: at least ten planted flaws of at
  least three kinds, each with a complete typed reason; a clean distractor; a clean
  twin that plants nothing and in which the package's own figure audit finds no
  comparison at all; all four perturbation probes; every planted figure recomputed by
  the package's own arithmetic from the rendered text (never Shimmer's computing
  layer) and found exactly as keyed, with no unintended comparison anywhere;
- the same seed gives byte-identical files, also in a separate process under a
  different string-hash seed;
- a planted flaw removed from the key is caught, as is a twin left with its flaws, a
  digit in a text value, and a missing probe;
- the slug and unit id rule matches the published examples; no generator source file
  name matches a credential or key ignore pattern.

The generators are not shipped in the container image, so when benchmark/generators/
is absent every case is skipped with the reason, never failed. Every case writes only
inside temporary folders.
"""
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
         ("f6", 17, {}), ("f5", 17, {"long_range": True})]
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
            out = os.path.join(cls.tmp, "a", "%s_%s_%d" % (fam, seed, len(opts)))
            cls.g.bundle.write_test(test, out)
            cls.written[(fam, bool(opts))] = out

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _read(self, fam, lr=False):
        return self.g.bundle.read_test(self.written[(fam, lr)])

    def _roles(self, test):
        return self.g.bundle._roles(test)

    def test_every_family_validates_from_disk(self):
        for fam, _, opts in FIXED:
            test = self._read(fam, bool(opts))
            errs = self.g.bundle.validate_test(test)
            self.assertEqual(errs, [], "%s %s: %s" % (fam, opts, errs[:5]))
            roles = self._roles(test)
            key = json.loads(test[roles["base"]]["answer_key.json"])
            flaws = key.get("planted") or key.get("band_irregularities")
            self.assertGreaterEqual(len(flaws), 10)
            self.assertGreaterEqual(len({f["kind"] for f in flaws}), 3)
            self.assertGreaterEqual(len(key["clean"]), 1)
            self.assertEqual(sorted(roles), sorted(["base", "twin"] + list(self.g.bundle.PROBES)))
            if opts.get("long_range"):
                self.assertTrue(all(e.get("related_unit") for e in key["planted"]))

    def test_same_seed_gives_identical_bytes(self):
        for fam, seed, opts in FIXED:
            out = os.path.join(self.tmp, "b", "%s_%s_%d" % (fam, seed, len(opts)))
            self.g.bundle.write_test(self.g.generate(fam, seed, **opts), out)
            first = _tree_bytes(self.written[(fam, bool(opts))])
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
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              env=env, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        self.assertEqual(proc.stdout.strip(), here)

    def test_removed_planted_flaw_is_caught(self):
        for fam, _, opts in FIXED:
            test = self._read(fam, bool(opts))
            base = self._roles(test)["base"]
            key = json.loads(test[base]["answer_key.json"])
            field = "planted" if "planted" in key else "band_irregularities"
            key[field] = key[field][1:]
            test[base]["answer_key.json"] = json.dumps(key)
            errs = self.g.bundle.validate_test(test)
            self.assertTrue(any("unintended comparison" in e or "band findings differ" in e
                                for e in errs), "%s: %s" % (fam, errs[:3]))

    def test_twin_left_with_its_flaws_is_caught(self):
        for fam in ("f1", "f3", "f6"):
            test = self._read(fam)
            roles = self._roles(test)
            base, twin = test[roles["base"]], test[roles["twin"]]
            bdoc = json.loads(base["answer_key.json"])["document"]
            tdoc = json.loads(twin["answer_key.json"])["document"]
            twin["context/" + tdoc] = base["context/" + bdoc]
            errs = self.g.bundle.validate_test(test)
            self.assertTrue(any(e.startswith(roles["twin"]) and "unintended comparison" in e
                                for e in errs), "%s: %s" % (fam, errs[:3]))

    def test_digit_in_a_text_value_is_refused(self):
        test = self._read("f2")
        base = self._roles(test)["base"]
        doc = "context/" + json.loads(test[base]["answer_key.json"])["document"]
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
        """D-025: the audit reads sentences, renames and attribution as the format now says."""
        au, tr = self.g.bundle.au, self.g.bundle.tr
        text = ("# T\n\nWindow note: standard\nWindow length: 48 hours\n\n"
                "The standard reply window is 48 hours. Then a reply follows!\n| a | b |\n")
        self.assertEqual(au.reader_sentences(text),
                         ["Window note: standard Window length: 48 hours",
                          "The standard reply window is 48 hours.", "Then a reply follows!"])
        self.assertEqual(len(tr.numbers_with_measures("Logged: 2026-03-01")), 3)
        conv = ("# C\n\nThese rules govern the clauses.\n\n"
                "## CONV-XA Other [required] [conformance]\n\n"
                "The other term must lie between 1 box and 9 box.\n\n"
                "## CONV-XB New [required] [conformance]\n\n"
                "The new charge must lie between 50 box and 200 box.\n")
        prior = "# T\n\n## Clause Alpha\n\nOld charge: 100 box\nOther term: 5 box\n"
        for now, renamed in (("102.04", True), ("102", True), ("98", True), ("97.96", False)):
            target = "# T\n\n## Clause Alpha\n\nNew charge: %s box\nOther term: 5 box\n" % now
            res = au.audit(target, "t.md", conv, "c.md", {"p.md": prior}, "p.md")
            self.assertEqual(res["errors"], [])
            records, refusals = au.prior_records(res)
            absent = [r for r in records if r["relation"] == "absent_since_prior"]
            self.assertEqual(("possible rename", "old charge") in refusals, renamed, now)
            self.assertEqual(bool(absent), not renamed, now)
        rules = [{"id": "A", "named": ["line total"]}, {"id": "B", "named": ["line total sum"]}]
        self.assertEqual(au._attribute(rules, "line total", "sum of 3 values under line"),
                         ("B", None))

    def test_no_source_name_matches_a_trap_pattern(self):
        traps = ("*key*", "*config*.py", "*secret*", "*credential*")
        for dirpath, dirs, names in os.walk(GEN):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for n in names:
                self.assertFalse(any(fnmatch.fnmatch(n.lower(), t) for t in traps), n)


def _flatten(test):
    return {"%s/%s" % (folder, path): text for folder, files in test.items()
            for path, text in files.items()}


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
                    "every figure recomputed with no unintended comparison); the same seed "
                    "gives identical bytes, also in a second process; a removed planted flaw, "
                    "a flawed twin, a digit in a text value and a missing probe are caught; "
                    "ids follow the published slug rule; the audit joins a paragraph's lines "
                    "into sentences, counts a date as three numbers, refuses a rename within "
                    "2%% of the larger figure and scores the basis words; no source name "
                    "matches a trap pattern" % result.testsRun)


if __name__ == "__main__":
    unittest.main()
