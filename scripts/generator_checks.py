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
  name matches a credential or key ignore pattern;
- family 4, two and three rounds, as a declared multi-round case (after S2): every
  bundle's case manifest is accepted by the controller's own validate_live_case_manifest
  on the documents the bound pipeline's _load_corpus loads, and by the generator's
  restatement of its rules, and both refuse every mutation in MUTATIONS and accept every
  harmless one; Shimmer's per-round review (multi_round_rounds.review_rounds) reuses
  exactly the units the key names and computes the key's band irregularities in the last
  round; Shimmer's own absent_checks (S2b item 5) mints and refuses exactly what the key's
  prior records and rename probes say, on the generated versions and on RENAME_CASES;
- each of those parts is neutralised in process (NEUTRALISATIONS: the generator's
  case validator, its spans, its reuse prediction, its rename refusal), caught on an
  unvalidated build, restored, and passes again.

The generators are not shipped in the container image, so when benchmark/generators/
is absent every case is skipped with the reason, never failed. Every case writes only
inside temporary folders. Shimmer's code is imported read-only by the agreement cases;
the generators themselves never import it.
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
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              env=env, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        self.assertEqual(proc.stdout.strip(), here)

    def test_removed_planted_flaw_is_caught(self):
        for fam, _, opts in FIXED:
            test = self._read(fam, **opts)
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
            # S2b item 5: outside the 2% window the newcomer is still a possible
            # successor in the same measure, so the old label is never withdrawn.
            self.assertEqual(("possible successor", "old charge") in refusals, not renamed, now)
            self.assertEqual(absent, [], now)
        for case in RENAME_CASES:
            if case[3]:
                self.assertEqual(_audit_rename_outcomes(au, case), case[2], case)
        rules = [{"id": "A", "named": ["line total"]}, {"id": "B", "named": ["line total sum"]}]
        self.assertEqual(au._attribute(rules, "line total", "sum of 3 values under line"),
                         ("B", None))

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

    def test_round_review_agrees_with_the_key(self):
        """Shimmer's per-round review (multi_round_rounds.review_rounds) reuses exactly the
        units the key's round_reuse names, and its last round computes exactly the key's
        band irregularities (none on the twin)."""
        ok, detail = observe_round_review(self.g, self._f4_tests())
        self.assertTrue(ok, detail)

    def test_rename_probes_agree_with_the_rename_refusal(self):
        """Every rename-probe kind is in every family 4 key with a typed reason, and
        Shimmer's own absent_checks (S2b item 5) mints and refuses exactly what the key
        says, on the generated versions and on the RENAME_CASES fixtures."""
        ok, detail = observe_rename_refusals(self.g, self._f4_tests())
        self.assertTrue(ok, detail)

    def test_neutralised_generator_parts_are_caught(self):
        """Neutralise, fail, restore, pass for each part the three checks above hold,
        each on an unvalidated build (bundle.build_bundles), so the controller and
        Shimmer's own code are what catch it, not the generator's self-validation."""
        for name, observe, patch_target, replacement in NEUTRALISATIONS:
            obj, attr = _resolve(self.g, patch_target)
            original = getattr(obj, attr)
            ok, detail = observe(self.g, [_unvalidated(self.g)])
            self.assertTrue(ok, "%s before: %s" % (name, detail))
            setattr(obj, attr, replacement(original))
            try:
                ok, detail = observe(self.g, [_unvalidated(self.g)])
            finally:
                setattr(obj, attr, original)
            self.assertFalse(ok, "%s: the neutralised part was not caught" % name)
            ok, detail = observe(self.g, [_unvalidated(self.g)])
            self.assertTrue(ok, "%s restored: %s" % (name, detail))


# ---- helpers for the multi-round case checks ----------------------------------------

# (prior label lines, target label lines, {earlier label: outcome}, audited) in one
# section; the outcome is possible_rename, possible_successor or absent (absent_since_prior
# minted). Shimmer decides every case; the generator's audit decides those it can read (a
# figure with no measure is outside the subset the generators write).
RENAME_CASES = [
    (["Old charge: 100 box"], ["New charge: 102.04 box"], {"old charge": "possible_rename"}, True),
    (["Old charge: 100 box"], ["New charge: 97.96 box"], {"old charge": "possible_successor"}, True),
    (["Old charge: 100 box"], ["New charge: 140 box"], {"old charge": "possible_successor"}, True),
    (["Old charge: 100 box"], ["New charge: 140 kg"], {"old charge": "absent"}, True),
    (["Old charge: 100 box", "Old levy: 300 box"], ["New charge: 101 box"],
     {"old charge": "possible_rename", "old levy": "absent"}, True),
    (["Old count: 100"], ["New count: 140"], {"old count": "possible_successor"}, False),
    (["Old charge: 100 box"], [], {"old charge": "absent"}, True),
]


def _rename_texts(case):
    prior_lines, target_lines = case[:2]
    body = "# T\n\n## Clause Alpha\n\n%s\n"
    prior = body % "\n".join(prior_lines + ["Other term: 5 box"])
    target = body % "\n".join(target_lines + ["Other term: 5 box"])
    rules = ["## CONV-XA Other [required] [conformance]\n\nThe other term must be stated."]
    for i, ln in enumerate(target_lines):
        label = ln.split(":")[0].lower()
        rules.append("## CONV-X%s New [required] [conformance]\n\nThe %s must be stated."
                     % (chr(ord("B") + i), label))
    conv = "# C\n\nThese rules govern the clauses.\n\n" + "\n\n".join(rules) + "\n"
    return prior, target, conv


def _audit_rename_outcomes(au, case):
    prior, target, conv = _rename_texts(case)
    res = au.audit(target, "t.md", conv, "c.md", {"p.md": prior}, "p.md")
    if res["errors"]:
        return {"errors": res["errors"]}
    records, refusals = au.prior_records(res)
    out = {lab: why.replace(" ", "_") for why, lab in refusals}
    out.update({r["field_label"]: "absent" for r in records if r["relation"] == "absent_since_prior"})
    return out


def _shimmer_path():
    for sub in ("scripts", "tools"):
        p = str(ROOT / sub)
        if p not in sys.path:
            sys.path.insert(0, p)


def shimmer_rename_outcomes(target_text, prior_text):
    """{earlier label: outcome} from Shimmer's own prior index, lookup and absent_checks,
    called unit by unit as the pipeline's prior comparison calls them (every paragraph
    given a REF id)."""
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
            reason = r["reason"]
            out[r["label"]] = ("possible_rename" if reason.startswith("possible rename, not a")
                               else "possible_successor" if reason.startswith("possible rename")
                               else reason)
    return out


def _bundle_texts(files):
    man = json.loads(files["context/_review_targets.json"])
    return files["context/" + man["targets"][0]], files["context/" + man["prior"][0]]


def observe_rename_refusals(g, tests):
    kinds = set(g.bundle.RENAME_PROBE_KINDS)
    for case in RENAME_CASES:
        prior, target, _ = _rename_texts(case)
        got = shimmer_rename_outcomes(target, prior)
        if got != case[2]:
            return False, "fixture %r: Shimmer %r" % (case[:2], got)
    n = 0
    for test in tests:
        for folder, files in sorted(test.items()):
            key = json.loads(files["answer_key.json"])
            rows = key.get("rename_probes", [])
            if {r["kind"] for r in rows} != kinds or not all(r.get("reason") for r in rows):
                return False, "%s: rename probe kinds or reasons" % folder
            absent = {r["field_label"]: "absent" for r in key["prior_records"]
                      if r["relation"] == "absent_since_prior"}
            refused = {r["field_label"]: r["reason"] for r in rows if r["kind"].startswith("renamed_")}
            if set(absent) & set(refused):
                return False, "%s: the key withdraws a term it also refuses as renamed" % folder
            want = dict(absent, **refused)
            got = shimmer_rename_outcomes(*_bundle_texts(files))
            if got != want:
                return False, "%s: Shimmer %r, key %r" % (folder, got, want)
            n += 1
    return True, "%d bundles" % n


def _controller():
    _shimmer_path()
    import ordinary_final_run
    return ordinary_final_run


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
    import copy
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
        s0["unit_id"] = "u01 clause"
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


class _Ctx:
    """The two things review_rounds reads from a run context."""

    def __init__(self, root):
        self.project_root = root

    def audit_dir(self):
        return Path(self.project_root) / "audit"


def observe_round_review(g, tests):
    _shimmer_path()
    import convention_parser
    import multi_round_rounds
    ofr = _controller()
    source = (ROOT / "scripts" / "pipeline.py").read_bytes()
    n, reused = 0, 0
    for test in tests:
        for folder, files in sorted(test.items()):
            key = json.loads(files["answer_key.json"])
            case = json.loads(files[g.bundle.mc.FILE])
            docs = ofr.case_corpus_documents(_context_members(files), source)
            with tempfile.TemporaryDirectory(prefix="gen_rounds_") as td:
                conv = Path(td) / "input" / "conventions"
                conv.mkdir(parents=True)
                for p, t in files.items():
                    if p.startswith("conventions/"):
                        (conv / p.split("/", 1)[1]).write_text(t, encoding="utf-8", newline="\n")
                registry = convention_parser.parse_conventions(Path(td)).as_dict()
                record = multi_round_rounds.review_rounds(
                    _Ctx(td), case, [{"id": k, "name": k, "text": v} for k, v in docs.items()],
                    convention_registry=registry)
            got = [{"round_id": r["round_id"], "unit_id": u["unit_id"],
                    "from_round": u["reused_from"]["round_id"], "from_unit": u["reused_from"]["unit_id"]}
                   for r in record["rounds"] for d in r["documents"] for u in d["units"]
                   if u["status"] == "reused"]
            if got != key["round_reuse"]:
                return False, "%s: Shimmer reuses %s, key %s" % (folder, got, key["round_reuse"])
            last = record["rounds"][-1]["documents"][0]["findings"]
            have = sorted((f["unit_id"], f["relation"], f.get("field_label"), round(float(f["value_a"]), 6),
                           round(float(f["value_b"]), 6)) for f in last)
            want = sorted((b["unit_id"], b["relation"], b["field_label"], round(float(b["value_a"]), 6),
                           round(float(b["value_b"]), 6)) for b in key["band_irregularities"])
            # The reworded-labels probe is checked for form only: by design its rules
            # stop pairing through the reworded label (INPUT_FORMAT section 11.1).
            if have != want and key.get("probe") != "reworded_labels":
                return False, "%s: last-round findings %s, key %s" % (
                    folder, sorted(set(have) ^ set(want)), len(want))
            n += 1
            reused += len(got)
    if not reused:
        return False, "no round reused a unit"
    return True, "%d bundles, %d reused units" % (n, reused)


def _unvalidated(g, seed=17):
    """A three-round family 4 test built but not self-validated."""
    return g.bundle.build_bundles(g.build_spec("f4", seed, rounds=3))


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


def _naive_reuse(_original):
    def reuse(round_texts, parse):
        out, first = [], {}
        for i, text in enumerate(round_texts, start=1):
            for uid, body in g_unit_texts(text):
                if body in first:
                    out.append({"round_id": "r%d" % i, "unit_id": uid,
                                "from_round": first[body][0], "from_unit": first[body][1]})
                else:
                    first[body] = ("r%d" % i, uid)
        return out
    return reuse


def g_unit_texts(text):
    return _load().multi_round_case.unit_texts(text)


# (name, observation, generator attribute neutralised, replacement factory)
NEUTRALISATIONS = [
    ("the generator's case-manifest validator accepts anything", observe_case_agreement,
     "multi_round_case.validate", lambda orig: (lambda *a, **k: [])),
    ("the case spans are one character off", observe_case_agreement,
     "multi_round_case.build", _shift_spans),
    ("the reuse prediction ignores the field vocabulary", observe_round_review,
     "multi_round_case.round_reuse", _naive_reuse),
    ("the rename refusal no longer refuses a moved rename", observe_rename_refusals,
     "bundle.au.possible_successor", lambda orig: (lambda *a, **k: False)),
]


def _tag(opts):
    return "_".join("%s-%s" % kv for kv in sorted(opts.items())) or "plain"


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
                    "2%% of the larger figure, refuses a moved rename as a possible successor "
                    "and scores the basis words; no source name matches a trap pattern; "
                    "family 4's case manifests (two and three rounds) are accepted by the "
                    "controller and the generator alike, %d mutations refused by both; "
                    "Shimmer's round review reuses the keyed units and finds the keyed "
                    "band breaches; Shimmer's rename refusal agrees with every rename probe; "
                    "four neutralisations caught and restored"
                    % (result.testsRun, len(MUTATIONS)))


if __name__ == "__main__":
    unittest.main()
