"""Checks for the two baseline arms under benchmark/baselines/ (loop stage S4f), run by
the verify gate (scripts/verify_session1.py) through check(); check_python_only() and
check_bare_model() run one arm, and `py -3.12 -X utf8 scripts/baseline_checks.py` runs
them by hand.

B2 (``python_only.py``) runs Shimmer's computing layer on a synthetic bundle and
must make ZERO model calls: every backend function of AgentWrapper (call_claude,
call_gpt, call_qwen, call_local, dispatch, run_task), the classifier's predict and
the reply-record writer are replaced by mocks that fail when touched. It must still
find the planted product mismatch, list the plan a model would have been asked under
``ablation_not_asked``, write the pipeline's completion record (read back by
scripts/run_completion.read as completed), and mark every file it writes as an
ablation on its first line (a JSON file's first key on the line of its opening brace,
D-039 item 17). Every record it writes
carries the provenance the pipeline gives Python's findings (envelope backend paired,
model python; the WRITTEN-BY-A stamp ``written_by: python``), and the adapters' mapping
reads the catch layer of its FLAG as computed.

B1 (``bare_model.py``) runs with a mocked model backend (no model load) and must write
EXACTLY ONE reply record per item through reply_records.write, joined to the item's
typed label by call id, including the item whose call fails, and never ask an item of
another document. It must load and verify the model once before the first item and
stop, generating nothing, when the load fails, the loaded identity differs from the
recorded values, a prompt plus the allowance exceeds the context, or a reply record
cannot be written. It records, per item and per benchmark, a reply whose length reached
the output allowance, and flags a parse rate below the 95 percent development floor.
Its parser (escape repair, UNCERTAIN), its prompt (revision 3, word for word against the
preregistration, rendered by benchmark/adapters/common/prompt.py, with the undecided
invitation only where the rule template asks for UNCERTAIN, and with the bundle's
reference material), its use of the one cut rule (benchmark/adapters/common/
cut.py; it carries none of its own) and its reading of the reading agent's model and
decoding policy from the tracked configuration are checked beside it.

Neither tool may import a model library: that is checked in a fresh subprocess, so a
library the gate process already imported cannot hide an import.

Every case runs in a temporary directory and writes nothing under config/, durable/,
ontology/ or output/. benchmark/ is not shipped in the container image, so with
benchmark/baselines/ absent every case is SKIPPED with the reason, never failed.
"""
import contextlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "benchmark" / "baselines"
FIXTURES = BASELINES / "fixtures"
BUNDLE = FIXTURES / "bundle_q4"
ITEMS = FIXTURES / "items_q4.json"
REPLIES = FIXTURES / "b1_replies.json"
PREREGISTRATION = ROOT / "docs" / "benchmarks" / "PREREGISTRATION.md"
MODEL_LIBRARIES = ("torch", "transformers", "peft", "bitsandbytes", "sentence_transformers")
ABSENT_REASON = "benchmark/baselines/ is not present here (the container image ships no benchmark/)"


def _load(name):
    path = BASELINES / (name + ".py")
    spec = importlib.util.spec_from_file_location("baseline_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _absent(base=None):
    base = Path(base) if base is not None else BASELINES
    return not (base / "python_only.py").is_file() or not (base / "bare_model.py").is_file()


EXPECTED = {"model_id": "fixture-model", "digest": "fixture-digest", "decoding": {}}


class FakeBackend:
    """A mocked model: canned replies by item id, one token per word."""

    def __init__(self, replies, identity=None, context=100000, fail_prepare=False):
        self.replies, self.identity, self.context = replies, identity or dict(EXPECTED), context
        self.fail_prepare, self.asked, self.users, self.prepared = fail_prepare, [], {}, 0

    def prepare(self):
        self.prepared += 1
        if self.fail_prepare:
            raise RuntimeError("fixture load failure")
        return dict(self.identity)

    def count_prompt(self, system, user):
        return len((system + " " + user).split())

    def max_context(self):
        return self.context

    def generate(self, system, user, max_new_tokens):
        item_id = next(i for i in self.replies if ("Item id: %s\n" % i) in user)
        self.asked.append(item_id)
        self.users[item_id] = user
        self.systems = getattr(self, "systems", {})
        self.systems[item_id] = system
        if self.replies[item_id].get("raise"):
            raise RuntimeError("fixture failure")
        reply = self.replies[item_id]["reply"]
        # one token per word, unless the case states the length (a reply cut at the allowance)
        tokens = self.replies[item_id].get("output_tokens", len(reply.split()))
        return {"text": reply, "payload": system + "\n" + user, "form": "fixture_messages",
                "output_tokens": tokens}


_SUBPROCESS = r"""
import json, sys, tempfile
from pathlib import Path
root = Path(sys.argv[1])
for p in (root / "scripts", root / "benchmark" / "baselines", root / "benchmark" / "adapters"):
    sys.path.insert(0, str(p))
import python_only, bare_model
replies = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))["replies"]
class Fake:
    def prepare(self): return {"model_id": "m", "digest": "d", "decoding": {}}
    def count_prompt(self, s, u): return 1
    def max_context(self): return 10
    def generate(self, s, u, n):
        i = next(k for k in replies if ("Item id: %s\n" % k) in u)
        return {"text": replies[i].get("reply", ""), "payload": u, "form": "f"}
with tempfile.TemporaryDirectory() as tmp:
    python_only.run(sys.argv[2], Path(tmp) / "b2")
    reader = {"agent": "X", "agent_source": "argument", "backend": "local_producer", "model_id": "m",
              "model_mode": "base", "max_new_tokens": 1, "max_new_tokens_source": "argument",
              "decoding": {"status": "s", "source": "s", "sha256": "s", "kwargs": {}}}
    bare_model.run(sys.argv[2], sys.argv[4], Path(tmp) / "b1", backend=Fake(), reader=reader,
                   development=True)
print(json.dumps(sorted(m for m in sys.argv[5].split(",") if m in sys.modules)))
"""


def _imports_in_subprocess():
    """The model libraries a fresh process holds after importing both tools and running
    each once (B1 on a mocked backend)."""
    out = subprocess.run([sys.executable, "-X", "utf8", "-c", _SUBPROCESS, str(ROOT), str(BUNDLE),
                          str(REPLIES), str(ITEMS), ",".join(MODEL_LIBRARIES)],
                         capture_output=True, text=True, encoding="utf-8", timeout=600)
    if out.returncode != 0:
        raise AssertionError("subprocess failed: " + (out.stderr.strip().splitlines() or ["?"])[-1])
    return json.loads(out.stdout.strip().splitlines()[-1])


@contextlib.contextmanager
def _no_model_calls():
    """Every route to a model replaced by a mock that raises; yields the mocks."""
    import agent_wrapper
    import auditor_pairs
    import reply_records
    mocks = {}
    with contextlib.ExitStack() as stack:
        for name in ("call_claude", "call_gpt", "call_qwen", "call_local", "dispatch", "run_task"):
            mocks[name] = stack.enter_context(mock.patch.object(
                agent_wrapper.AgentWrapper, name, side_effect=AssertionError("model call: " + name)))
        mocks["predict"] = stack.enter_context(mock.patch.object(
            auditor_pairs, "predict", side_effect=AssertionError("model call: predict")))
        mocks["reply_records.write"] = stack.enter_context(mock.patch.object(
            reply_records, "write", side_effect=AssertionError("reply record written")))
        yield mocks


def _config_snapshot():
    return {p.name: p.stat().st_mtime_ns for p in (ROOT / "config").iterdir() if p.is_file()}


class PythonOnlyChecks(unittest.TestCase):
    def setUp(self):
        if _absent():
            self.skipTest(ABSENT_REASON)
        self.tool = _load("python_only")

    def test_zero_model_calls_and_marked_output(self):
        config_before = _config_snapshot()
        with tempfile.TemporaryDirectory(prefix="b2_check_") as tmp:
            out = Path(tmp) / "out"
            with _no_model_calls() as mocks:
                status = self.tool.run(BUNDLE, out)
            touched = {k: m.call_count for k, m in mocks.items() if m.call_count}
            self.assertEqual(touched, {}, "B2 reached a model route")
            self.assertEqual(status["model_calls"], 0)
            self.assertEqual(status["state"], "completed")
            self.assertFalse(list(out.rglob("model_replies")), "B2 wrote reply records")
            written = sorted(p for p in out.rglob("*") if p.is_file())
            self.assertTrue(written)
            for path in written:
                text = path.read_text(encoding="utf-8")
                if path.suffix == ".json":
                    self.assertEqual(next(iter(json.loads(text))), "ablation", path.name)
                    self.assertTrue(text.splitlines()[0].startswith('{"ablation": "ABLATION'), path.name)
                else:
                    self.assertTrue(text.splitlines()[0].startswith("ABLATION"), path.name)
            with self.assertRaisesRegex(ValueError, "starts with its ablation statement"):
                self.tool._write_json(Path(tmp) / "x.json", {"state": "completed", "ablation": "x"})
            data = json.loads((out / "deliverables" / "dq4" / "review_data.json").read_text(encoding="utf-8"))
            irregular = [f for f in data["findings"] if f.get("record_verdict") == "irregular"]
            self.assertEqual([(f["relation"], f["source_rule_id"], f["value_a"], f["value_b"])
                              for f in irregular],
                             [("product_mismatch", "CONV-QA-01", 48.0, 52.0)])
            self.assertEqual(len(data["amendments"]), 1)
            sys.path.insert(0, str(ROOT / "scripts"))
            import run_completion
            completion = run_completion.read(out)
            self.assertIsNotNone(completion, "B2 wrote a valid completion record")
            self.assertEqual((completion["state"], completion["reached_end"], completion["exit_code"]),
                             ("completed", True, 0))
            pairing = json.loads((out / "audit" / "pairing_map.json").read_text(encoding="utf-8"))["dq4"]
            self.assertEqual(pairing["calls_made"], 0)
            self.assertEqual([(r["unit_id"], r["source_rule_id"], r["kind"])
                              for r in pairing["ablation_not_asked"]],
                             [("u03-p-00003", "CONV-QA-02", "uncomputable")])
        self.assertEqual(_config_snapshot(), config_before, "B2 changed a config file")

    def test_records_carry_python_provenance(self):
        # Every record B2 writes is Python's: its envelope carries the pipeline's computed
        # post (backend paired, model python) and each record the WRITTEN-BY-A stamp
        # decided from it, so the adapters read the catch layer as Python's (computed).
        self.assertEqual([self.tool.written_by(b, m) for b, m in (
            ("paired", "python"), ("computed", "python-x"), ("paired", "python+model"),
            ("paired", "qwen"), ("local", "python"), (None, None))],
            ["python", "python", "python", "model", "model", "model"])
        with tempfile.TemporaryDirectory(prefix="b2_layer_") as tmp:
            out = Path(tmp) / "runs" / "dq4"
            with _no_model_calls():
                status = self.tool.run(BUNDLE, out)
            self.assertEqual(status["documents"]["dq4"]["posts"],
                             [{"agent": status["documents"]["dq4"]["posts"][0]["agent"],
                               "backend": "paired", "model": "python", "items": 1}])
            data = json.loads((out / "deliverables" / "dq4" / "review_data.json").read_text(encoding="utf-8"))
            self.assertTrue(data["findings"])
            self.assertEqual({f.get("written_by") for f in data["findings"]}, {"python"})
            sys.path.insert(0, str(ROOT / "benchmark" / "adapters"))
            try:
                from common import mapping
            finally:
                sys.path.remove(str(ROOT / "benchmark" / "adapters"))
            spec = mapping.Spec("findver", labels={mapping.FLAG: "refuted", mapping.CLEAR: "entailed",
                                                   mapping.UNDECIDED: None},
                                b1_labels={"refuted": mapping.FLAG})
            items = [{"item_id": "a1", "document_id": "dq4", "rule_id": "CONV-QA-01"}]
            row = mapping.label_pipeline_arm(spec, items, Path(tmp) / "runs", arm="B2")["labels"][0]
            self.assertEqual((row["class"], row["layer"]), ("FLAG", "computed"))

    def test_no_model_library_in_a_fresh_process(self):
        self.assertEqual(_imports_in_subprocess(), [], "a baseline tool imported a model library")


class BareModelChecks(unittest.TestCase):
    def setUp(self):
        if _absent():
            self.skipTest(ABSENT_REASON)
        self.tool = _load("bare_model")
        self.spec = self.tool.load_prompt()

    def _reader(self):
        with mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "base"}):
            return self.tool.resolve_reader(ROOT, max_new_tokens=64)

    def test_one_reply_record_per_item(self):
        import reply_records
        replies = json.loads(REPLIES.read_text(encoding="utf-8"))["replies"]
        backend = FakeBackend(replies)
        with tempfile.TemporaryDirectory(prefix="b1_check_") as tmp:
            out = Path(tmp) / "out"
            summary = self.tool.run(BUNDLE, ITEMS, out, backend=backend, reader=self._reader(),
                                    run_id="b1-fixture", expected=EXPECTED)
            self.assertEqual(backend.prepared, 1, "the model is prepared once, before the first item")
            self.assertEqual(sorted(backend.asked), sorted(replies), "items asked")
            records = reply_records.records(out / "audit" / "model_replies")
            labels = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                      for p in (out / "labels").glob("*.json")}
            self.assertEqual(len(records), len(replies), "one reply record per item")
            self.assertEqual(sorted(labels), sorted(replies), "one label per item")
            self.assertEqual(sorted(r["call_id"] for r in records),
                             sorted(l["call_id"] for l in labels.values()), "records join labels")
            for record in records:
                self.assertEqual((record["doc_id"], record["run_id"], record["phase"]),
                                 ("dq4", "b1-fixture", "B1"))
                self.assertEqual(record["decoding"]["max_new_tokens"], 64)
            failed = [r for r in records if not r["backend_ok"]]
            self.assertEqual(len(failed), 1)
            self.assertIsNone(failed[0]["reply"])
            for item_id, entry in replies.items():
                got = labels[item_id]
                self.assertEqual({k: got[k] for k in entry["expect"]}, entry["expect"], item_id)
                self.assertEqual(next(iter(got)), "baseline")
            sent = next(r for r in records if r["backend_ok"])["payload"]["text"]
            self.assertIn("REFERENCE MATERIAL\nNone.\n", sent)
            self.assertIn("Line total: 52 credit", sent)
            self.assertIn("CONV-QA-01 Total [required] [conformance]: The line total must equal", sent)
            rates = {k: v["parse_rate"] for k, v in summary["benchmarks"].items()}
            self.assertEqual(sorted(rates.values()), [0.0, 0.0, 1.0, 1.0])
            self.assertEqual({k: v["below_parse_rate_floor"] for k, v in summary["benchmarks"].items()},
                             {k: r < 0.95 for k, r in rates.items()})
            self.assertEqual(summary["verified_against"], ["decoding", "digest", "model_id"])
            # A reply whose length reached the allowance (64) is recorded, per item and counted.
            reached = {item_id: label["length_reached_allowance"] for item_id, label in labels.items()}
            for item_id, entry in replies.items():
                if entry.get("raise"):
                    self.assertIsNone(reached[item_id], item_id)
                else:
                    self.assertEqual(reached[item_id], entry.get("output_tokens", 0) >= 64, item_id)
            self.assertEqual(sum(v["length_reached_allowance"] for v in summary["benchmarks"].values()),
                             sum(1 for e in replies.values() if e.get("output_tokens", 0) >= 64))
            self.assertGreater(sum(1 for v in reached.values() if v), 0, "a fixture reply reaches the allowance")
            self.assertEqual(self.tool.length_reached({"text": "x"}, 64), None)

    def test_setup_failures_stop_before_anything_is_generated(self):
        import reply_records
        replies = json.loads(REPLIES.read_text(encoding="utf-8"))["replies"]
        cases = [
            ("load", FakeBackend(replies, fail_prepare=True), EXPECTED, RuntimeError),
            ("digest", FakeBackend(replies, identity=dict(EXPECTED, digest="other")), EXPECTED,
             self.tool.SetupError),
            ("unrecorded", FakeBackend(replies), None, self.tool.SetupError),
            ("context", FakeBackend(replies, context=50), EXPECTED, self.tool.SetupError),
        ]
        for name, backend, expected, error in cases:
            with tempfile.TemporaryDirectory(prefix="b1_stop_") as tmp:
                out = Path(tmp) / "out"
                with self.assertRaises(error, msg=name):
                    self.tool.run(BUNDLE, ITEMS, out, backend=backend, reader=self._reader(),
                                  expected=expected)
                self.assertEqual(backend.asked, [], name + ": nothing generated")
                self.assertFalse((out / "labels").exists(), name + ": no label written")
        with tempfile.TemporaryDirectory(prefix="b1_stop_") as tmp:
            backend = FakeBackend(replies)
            with mock.patch.object(reply_records, "write", return_value=None):
                with self.assertRaises(self.tool.SetupError):
                    self.tool.run(BUNDLE, ITEMS, Path(tmp) / "out", backend=backend,
                                  reader=self._reader(), expected=EXPECTED)
            self.assertEqual(len(backend.asked), 1, "the run stops at the first unrecorded reply")

    def test_reference_material_is_shown_and_sensitive_runs_keep_hashes(self):
        replies = json.loads(REPLIES.read_text(encoding="utf-8"))["replies"]
        with tempfile.TemporaryDirectory(prefix="b1_ref_") as tmp:
            bundle = Path(tmp) / "bundle"
            shutil.copytree(BUNDLE, bundle)
            (bundle / "context" / "ref_q4.md").write_text("# Reference\n\nA reference passage.\n",
                                                          encoding="utf-8")
            manifest = json.loads((bundle / "context" / "_review_targets.json").read_text(encoding="utf-8"))
            manifest["grounding"] = ["ref_q4.md"]
            (bundle / "context" / "_review_targets.json").write_text(json.dumps(manifest), encoding="utf-8")
            backend = FakeBackend(replies)
            out = Path(tmp) / "out"
            summary = self.tool.run(bundle, ITEMS, out, backend=backend, reader=self._reader(),
                                    expected=EXPECTED, sensitive=True)
            self.assertTrue(summary["reference_material"])
            self.assertIn("REFERENCE MATERIAL\nref_q4.md\n# Reference\n\nA reference passage.\n\nITEM",
                          backend.users["a1"])
            label = json.loads((out / "labels" / "a1.json").read_text(encoding="utf-8"))
            self.assertIsNone(label["evidence"])
            self.assertEqual(set(label["evidence_hashed"]), {"sha256", "length_bytes"})
            self.assertNotIn("Line total: 52 credit", (out / "labels" / "a1.json").read_text(encoding="utf-8"))

    def test_parser(self):
        parse = self.tool.parse_reply
        for key, bench in self.spec["benchmarks"].items():
            names = self.tool.label_names(bench)
            first = names[0]
            reply = ("working\n```json\n" + json.dumps({"item_id": "x", "evidence": "{a}",
                     "reason": "r", "label": first.upper().replace(" ", "_") + ": gloss"}) + "\n```")
            self.assertEqual(parse(reply, bench, "x")["label"], first, key)
            undecided = json.dumps({"label": bench["undecided"] + " (undecided)"})
            self.assertEqual(parse("{\"label\": \"%s\"}\n%s" % (names[-1], undecided), bench)["label"],
                             bench["undecided"], key + " last object wins")
            self.assertFalse(parse(json.dumps({"label": "zzz"}), bench)["parsed"], key)
            self.assertFalse(parse("{\"label\": \"%s\"" % first, bench)["parsed"], key)
            self.assertFalse(parse("", bench)["parsed"], key)
            self.assertTrue(parse(json.dumps({"item_id": "other", "label": first}), bench, "x")["parsed"])
            # an invalid JSON escape in evidence costs nothing; a valid escaped pair is kept
            repaired = parse('{"evidence": "a \\| b \\\\ c \\cite", "label": "%s"}' % first, bench)
            self.assertEqual((repaired["label"], repaired["repaired"], repaired["evidence"]),
                             (first, True, "a \\| b \\ c \\cite"), key)
            self.assertEqual(parse('{"label": "UNCERTAIN"}', bench)["label"], bench["undecided"], key)

    def test_undecided_invitation_only_where_the_rule_asks_for_uncertain(self):
        # Revision 3 (D-039 item 5): the system turn invites the undecided label only on the
        # benchmarks whose rule template asks for UNCERTAIN (SciTab, ContractNLI); on the
        # others the undecided label stays listed and parsed but is not invited. Every
        # system turn says the headings and label lines are markup, not content.
        invitation = self.spec["undecided_invitation"]
        for key in self.spec["benchmarks"]:
            system = self.tool.render_system(self.spec, key)
            self.assertNotIn("{", system.split("JSON object")[0], key)
            self.assertEqual(invitation in system, key in ("scitab", "contractnli"), key)
            self.assertIn("are markup that divides it into passages, not content", system)
            self.assertNotIn("{undecided_invitation}", system)
            user = self.tool.render_user(self.spec, key, document="d", conventions=[], item={
                "item_id": "x", "rule_id": "CONV-X"})
            self.assertIn("The undecided label is: " + self.spec["benchmarks"][key]["undecided"], user)
        replies = json.loads(REPLIES.read_text(encoding="utf-8"))["replies"]
        backend = FakeBackend(replies)
        with tempfile.TemporaryDirectory(prefix="b1_inv_") as tmp:
            self.tool.run(BUNDLE, ITEMS, Path(tmp) / "out", backend=backend, reader=self._reader(),
                          expected=EXPECTED)
        items = {r["item_id"]: r["benchmark"] for r in json.loads(ITEMS.read_text(encoding="utf-8"))["items"]}
        for item_id, system in backend.systems.items():
            self.assertEqual(system, self.tool.render_system(self.spec, items[item_id]), item_id)

    def test_prompt_is_the_preregistered_text(self):
        if not PREREGISTRATION.is_file():
            self.skipTest("docs/benchmarks/PREREGISTRATION.md is not present here")
        prereg = PREREGISTRATION.read_text(encoding="utf-8")
        start = prereg.index("### 5.4")
        section = prereg[start:prereg.index("\n### ", start + 1)]
        self.assertIn(self.spec["source"], ("docs/benchmarks/PREREGISTRATION.md section 5.4",))
        system = self.spec["system"].replace("{undecided_invitation}", "{undecided invitation}")
        self.assertIn("```\n" + system + "\n```", section)
        self.assertIn("Undecided invitation: `%s`" % self.spec["undecided_invitation"], section)
        template = self.spec["user_template"]
        for slot, written in (("{document}", "{document, after the cut rule, as it stands in the bundle}"),
                              ("{conventions}", "{every convention in the bundle as written in it, one per line: its heading without the leading # characters, a colon, a space, then its text}"),
                              ("{reference_material}", "{the bundle's reference material: for each grounding file, the earlier version included, in file-name order, its file name on one line and its text below, the files separated by a blank line; the single line None. when there is none}"),
                              ("{item_id}", "{opaque item id}"), ("{rule_id}", "{the item's rule id}"),
                              ("{question}", "{the item's question line, below}"),
                              ("{label_lines}", "{the benchmark's label lines, below}"),
                              ("{undecided_label}", "{the benchmark's undecided label name}")):
            template = template.replace(slot, written)
        self.assertIn("```\n" + template + "\n```", section)
        for bench in self.spec["benchmarks"].values():
            self.assertIn("Question: `%s`" % bench["question"], section)
            self.assertIn("Labels: " + " / ".join("`%s`" % line for line in bench["labels"]), section)
            self.assertIn("Undecided label: `%s`. Invited: %s." % (
                bench["undecided"], "yes" if bench["invite_undecided"] else "no"), section)

    def test_one_cut_rule_and_one_renderer(self):
        for name in ("cut_document", "cut_budget", "cut_note", "prompt_overhead", "conventions_block"):
            self.assertFalse(hasattr(self.tool, name), "bare_model carries its own " + name)
        sys.path.insert(0, str(ROOT / "benchmark" / "adapters"))
        try:
            from common import cut, prompt
        finally:
            sys.path.remove(str(ROOT / "benchmark" / "adapters"))
        self.assertIs(self.tool.b1_prompt, prompt)
        self.assertEqual(cut.budget(1000, 100, 200), 668)
        count = lambda system, user: len(system.split()) + len(user.split())  # noqa: E731
        items = [{"item_id": "x", "rule_id": "CONV-X", "benchmark": key} for key in self.spec["benchmarks"]]
        conventions = [("CONV-X Name [required] [conformance]", "text")]
        longest = max(count(self.tool.render_system(self.spec, i["benchmark"]), self.tool.render_user(
            self.spec, i["benchmark"], document="", conventions=conventions, item=i)) for i in items)
        self.assertEqual(prompt.overhead(self.spec, items, conventions, count), longest)

    def test_reader_from_configuration(self):
        import decoding_policy
        reader = self._reader()
        with mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "base"}):
            plain = self.tool.resolve_reader(ROOT)
        chosen = json.loads((ROOT / "config" / "local_models.json").read_text(encoding="utf-8"))
        self.assertEqual((reader["agent"], reader["agent_source"]), ("PROCESSOR", "placeholder"))
        self.assertIn(reader["backend"], decoding_policy.LOCAL_BACKENDS)
        self.assertEqual(reader["model_id"], chosen["active_producer"])
        self.assertEqual(reader["decoding"], decoding_policy.policy(reader["backend"], ROOT))
        self.assertEqual(plain["max_new_tokens"],
                         self.tool.pipeline_literal("PRODUCTION_MAX_TOKENS"))
        self.assertEqual(plain["max_new_tokens_source"], "pipeline PRODUCTION_MAX_TOKENS")


class AbsentChecks(unittest.TestCase):
    def test_absent_folder_skips(self):
        with tempfile.TemporaryDirectory(prefix="b_absent_") as tmp:
            self.assertTrue(_absent(Path(tmp) / "benchmark" / "baselines"))


def _run(case):
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(case).run(result)
    return result


def _verdict(results, what):
    failures = sum(len(r.failures) + len(r.errors) for r in results)
    if failures:
        first = next(r.failures[0][1] if r.failures else r.errors[0][1] for r in results
                     if r.failures or r.errors)
        lines = first.strip().splitlines()
        cause = next((l for l in lines if l.split(":", 1)[0].endswith(("Error", "Exception"))),
                     lines[-1])
        return ("FAIL", "%d failures/errors; first: %s" % (failures, cause))
    ran = sum(r.testsRun - len(r.skipped) for r in results)
    skipped = [s for r in results for s in r.skipped]
    if _absent():
        return ("SKIP", ABSENT_REASON)
    note = ("; skipped: " + skipped[0][1]) if skipped else ""
    return ("PASS", "%d cases: %s%s" % (ran, what, note))


def check_python_only():
    return _verdict([_run(PythonOnlyChecks), _run(AbsentChecks)],
                    "B2 runs the computing layer on a mocked bundle with every model route "
                    "mocked to fail and touches none, imports no model library (fresh subprocess), "
                    "finds the planted product mismatch, lists the unasked plan, writes the "
                    "pipeline's completion record, marks every file an ablation, and stamps every "
                    "record written_by python from the pipeline's computed post (backend paired, "
                    "model python), which the adapters read as the computed layer")


def check_bare_model():
    return _verdict([_run(BareModelChecks), _run(AbsentChecks)],
                    "B1 with a mocked backend writes exactly one reply record per item (a failed "
                    "call included) joined to one typed label by call id, asks no item of another "
                    "document, prepares and verifies its model once and stops before generating on "
                    "a load, identity, context or record failure, parses the final-line JSON label "
                    "(escape repair, UNCERTAIN) or abstains, records replies that reach the output "
                    "allowance and flags a parse rate below 95 percent, sends the preregistered "
                    "prompt (revision 3: the undecided invitation only where the rule asks for "
                    "UNCERTAIN) with the reference material, uses the one cut rule in "
                    "common/cut.py, and reads its model and decoding policy from the tracked "
                    "configuration")


def check():
    results = [_run(PythonOnlyChecks), _run(BareModelChecks), _run(AbsentChecks)]
    return _verdict(results, "B2 makes no model call, imports no model library, writes the "
                             "pipeline's completion record and marks its output an ablation on each "
                             "file's first line; B1 verifies its model once and stops before "
                             "generating on any setup failure, writes one reply record per item, "
                             "parses (with escape repair) or abstains, records truncation and the "
                             "parse-rate floor, sends the preregistered prompt (revision 3) with "
                             "reference material, and uses the one cut rule and prompt renderer")


if __name__ == "__main__":
    print(check())
