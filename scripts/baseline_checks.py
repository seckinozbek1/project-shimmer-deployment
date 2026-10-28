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
the output allowance, and pools the parse rate per benchmark over every document's
summary, deciding the 95 percent development floor on the pooled rate (section 5.4).
Its parser (escape repair, UNCERTAIN), its prompt (revision 3, word for word against the
preregistration, rendered by benchmark/adapters/common/prompt.py, with the undecided
invitation only where the rule template asks for UNCERTAIN, and with the bundle's
reference material), its use of the one cut rule (benchmark/adapters/common/
cut.py; it carries none of its own) and its reading of the reading agent's model and
decoding policy from the tracked configuration are checked beside it.

B1's two checkpoints in final mode (loop plan S5, R20), on a mocked model and a fixture
base folder, no model load: `base` loads the pinned base through final_models.base_path
(base_hashes checked) and never applies the adapter nor reads an adapter file; `tuned`
goes through final_models.resident and applies it; a base hash mismatch refuses before
any model is loaded; each records its digest (revision plus model.safetensors SHA-256,
plus the adapter's for tuned), and run_b1, the in-process entry, records the checkpoint.

Neither tool may import a model library: that is checked in a fresh subprocess, so a
library the gate process already imported cannot hide an import.

Every case runs in a temporary directory and writes nothing under config/, durable/,
ontology/ or output/. benchmark/ is not shipped in the container image, so with
benchmark/baselines/ absent every case is SKIPPED with the reason, never failed.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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
# D-060 and D-061, written out here so the checks hold the tool to it: B1 follows the producer,
# eager, and prefills in chunks of 512 tokens under D-061 (E). No measurement decision: the run
# proper names none.
B1_ATTENTION = {"attention_implementation": "eager", "sdpa_backend": None,
                "attention_decision": None,
                "prefill": "chunked", "prefill_chunk_tokens": 512, "prefill_decision": "D-061"}
# D-056 condition 6 and D-061 item 4: an sdpa measurement pass, with the decision that asks
# for it (the memory-efficient backend pinned), and a one-shot measurement pass.
B1_SDPA = dict(B1_ATTENTION, attention_implementation="sdpa", sdpa_backend="EFFICIENT_ATTENTION",
               attention_decision="D-061")
B1_ONE_SHOT = dict(B1_ATTENTION, prefill="one_shot", prefill_chunk_tokens=None)


class FakeBackend:
    """A mocked model: canned replies by item id, one token per word. It reports B1's
    declared attention unless `attention` says otherwise (None: it reports none)."""

    def __init__(self, replies, identity=None, context=100000, fail_prepare=False,
                 attention=B1_ATTENTION, raise_for=None):
        self.replies, self.identity, self.context = replies, identity or dict(EXPECTED), context
        self.fail_prepare, self.asked, self.users, self.prepared = fail_prepare, [], {}, 0
        self.attention, self.raise_for = attention, raise_for or {}

    def prepare(self):
        self.prepared += 1
        if self.fail_prepare:
            raise RuntimeError("fixture load failure")
        identity = dict(self.identity)
        if self.attention is not None:
            identity.setdefault("attention", dict(self.attention))
        return identity

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
        if item_id in self.raise_for:
            raise self.raise_for[item_id]
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
    def prepare(self): return {"model_id": "m", "digest": "d", "decoding": {},
                               "attention": bare_model.attention_record()}
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
            self.assertEqual(summary["verified_against"], ["attention", "decoding", "digest", "model_id"])
            # D-056: the attention every call ran under, in every reply record and the summary
            self.assertEqual(summary["attention"], B1_ATTENTION)
            self.assertEqual([r["attention"] for r in records], [B1_ATTENTION] * len(records))
            self.assertEqual({l["attention"]["attention_implementation"] for l in labels.values()}, {"eager"})
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

    def test_parse_rate_floor_is_decided_on_the_pooled_rate(self):
        # Adversarial round 3, item 7: the 95 percent floor (section 5.4) is a benchmark's,
        # read on the rate pooled over all its development documents, not on any one
        # document's b1_summary.json. Here one benchmark has a document below the floor yet
        # pools to exactly 0.95 (not below), and another pools below it.
        docs = {"d1": {"findver": (30, 29)}, "d2": {"findver": (10, 9)},
                "d3": {"contradoc": (10, 10)}, "d4": {"contradoc": (10, 8)}}
        with tempfile.TemporaryDirectory(prefix="b1_pool_") as tmp:
            root = Path(tmp) / "runs"
            for doc, benches in docs.items():
                (root / doc).mkdir(parents=True)
                rows = {b: {"items": n, "parsed": p, "parse_rate": p / n,
                            "below_parse_rate_floor": p / n < 0.95} for b, (n, p) in benches.items()}
                (root / doc / "b1_summary.json").write_text(json.dumps({"benchmarks": rows}), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = self.tool.main(["pool", "--runs", str(root)])
            self.assertEqual(code, 0)
            pooled = json.loads((root / "b1_parse_rates.json").read_text(encoding="utf-8"))
            self.assertEqual(pooled["documents"], 4)
            got = {b: (r["items"], r["parsed"], r["below_parse_rate_floor"]) for b, r in pooled["benchmarks"].items()}
            self.assertEqual(got, {"findver": (40, 38, False), "contradoc": (20, 18, True)})
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(self.tool.main(["pool", "--runs", str(Path(tmp) / "empty")]), 4)

    def test_setup_failures_stop_before_anything_is_generated(self):
        import reply_records
        replies = json.loads(REPLIES.read_text(encoding="utf-8"))["replies"]
        cases = [
            ("load", FakeBackend(replies, fail_prepare=True), EXPECTED, RuntimeError),
            ("digest", FakeBackend(replies, identity=dict(EXPECTED, digest="other")), EXPECTED,
             self.tool.SetupError),
            ("unrecorded", FakeBackend(replies), None, self.tool.SetupError),
            ("context", FakeBackend(replies, context=50), EXPECTED, self.tool.SetupError),
            # D-056 condition 1: a backend that reports no attention, or another, stops the run
            ("no attention", FakeBackend(replies, attention=None), EXPECTED, self.tool.SetupError),
            ("sdpa attention", FakeBackend(replies, attention=dict(
                B1_ATTENTION, attention_implementation="sdpa")), EXPECTED, self.tool.SetupError),
            # D-061: a backend that loaded another prefill stops the run too
            ("one-shot prefill", FakeBackend(replies, attention=B1_ONE_SHOT), EXPECTED, self.tool.SetupError),
            ("math backend", FakeBackend(replies, attention=dict(B1_ATTENTION, sdpa_backend="MATH")),
             EXPECTED, self.tool.SetupError),
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


class _FakeModel:
    """A mocked 4-bit model: records what was done to it, loads nothing. Its config carries
    the attention it was loaded with, as transformers sets it from attn_implementation."""

    def __init__(self, attention=None):
        self.config = SimpleNamespace(model_type="qwen2", use_cache=False, quantization_config={
            "bnb_4bit_quant_type": "nf4", "bnb_4bit_compute_dtype": "bfloat16"},
            _attn_implementation=attention)
        self.is_loaded_in_4bit = True
        self.prepared_for_kbit = False

    def requires_grad_(self, flag):
        return self

    def eval(self):
        return self

    def gradient_checkpointing_disable(self):
        return self


class _FakeLibs:
    """transformers and peft stand-ins: count every load and every adapter application."""

    def __init__(self):
        self.calls = {"tokenizer": [], "model": [], "kbit": 0, "adapter": [], "attention": []}
        libs = self

        class AutoTokenizer:
            @staticmethod
            def from_pretrained(path, **kw):
                libs.calls["tokenizer"].append(path)
                return SimpleNamespace(path=path)

        class AutoModelForCausalLM:
            @staticmethod
            def from_pretrained(path, **kw):
                libs.calls["model"].append(path)
                libs.calls["attention"].append(kw.get("attn_implementation"))
                return _FakeModel(kw.get("attn_implementation"))

        class PeftModel:
            @staticmethod
            def from_pretrained(model, adapter_dir, **kw):
                libs.calls["adapter"].append(adapter_dir)
                wrapped = _FakeModel()
                wrapped.base = model
                return wrapped

        def prepare_model_for_kbit_training(model, **kw):
            libs.calls["kbit"] += 1
            model.prepared_for_kbit = True
            return model

        self.AutoTokenizer, self.AutoModelForCausalLM = AutoTokenizer, AutoModelForCausalLM
        self.PeftModel, self.prepare_model_for_kbit_training = PeftModel, prepare_model_for_kbit_training

    def modules(self):
        """sys.modules entries for the real final_models.load (the tuned path)."""
        transformers = SimpleNamespace(AutoTokenizer=self.AutoTokenizer,
                                       AutoModelForCausalLM=self.AutoModelForCausalLM)
        peft = SimpleNamespace(PeftModel=self.PeftModel,
                               prepare_model_for_kbit_training=self.prepare_model_for_kbit_training)
        return {"transformers": transformers, "peft": peft}


class CheckpointChecks(unittest.TestCase):
    """R20: in final mode B1 loads the tuned producer (base plus adapter, through
    final_models as the pipeline does) or the same pinned base WITHOUT the adapter, read
    through final_models.base_path with its base_hashes check. On a mocked model and a
    fixture base folder (no model load): base never applies the adapter and reads no adapter
    file; tuned does; a base hash mismatch refuses before any model is loaded; each records
    its digest (revision plus model.safetensors SHA-256, plus the adapter's for tuned)."""

    def setUp(self):
        if _absent():
            self.skipTest(ABSENT_REASON)
        self.tool = _load("bare_model")
        self.fm = final_models = self.tool.final_models
        self.tmp = tempfile.TemporaryDirectory(prefix="b1_ckpt_")
        root = Path(self.tmp.name)
        self.base = root / "base"
        self.base.mkdir()
        hashes = {}
        for name, text in (("config.json", "{}"), ("model.safetensors", "fixture weights")):
            (self.base / name).write_text(text, encoding="utf-8")
            hashes[name] = final_models.sha(self.base / name)
        adapter_dir = root / "adapter"
        adapter_dir.mkdir()
        for name in ("adapter_model.safetensors", "adapter_config.json"):
            (adapter_dir / name).write_text("fixture adapter", encoding="utf-8")
        self.adapter_dir = adapter_dir
        self.spec = {"checkpoint": 168, "model_id": "fixture/base-4bit", "revision": "rev-fixture",
                     "base_hashes": hashes,
                     "files": {"adapter": {"path": "x", "sha256": "a" * 64},
                               "adapter_config": {"path": "y", "sha256": "b" * 64}}}
        self.paths = {"adapter": adapter_dir / "adapter_model.safetensors",
                      "adapter_config": adapter_dir / "adapter_config.json"}

    def tearDown(self):
        self.tmp.cleanup()

    def _reader(self, checkpoint):
        with mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "final"}):
            return self.tool.resolve_reader(ROOT, max_new_tokens=64, checkpoint=checkpoint)

    @contextlib.contextmanager
    def _mocked(self, libs, *, verify_adapter=True):
        fake_torch = SimpleNamespace(bfloat16="bfloat16")
        verify = (mock.patch.object(self.fm, "verify", return_value=(self.spec, self.paths))
                  if verify_adapter else
                  mock.patch.object(self.fm, "verify", side_effect=AssertionError("adapter files read")))
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, {"SHIMMER_PRODUCER_BASE_PATH": str(self.base),
                                                             "SHIMMER_MODEL_MODE": "final"}))
            stack.enter_context(mock.patch.dict(sys.modules, libs.modules()))
            stack.enter_context(mock.patch.dict(self.fm._RESIDENTS, clear=True))
            stack.enter_context(mock.patch.object(self.fm, "verify_runtime", return_value=fake_torch))
            stack.enter_context(mock.patch.object(self.fm, "specification", return_value=self.spec))
            stack.enter_context(verify)
            yield

    def _backend(self, checkpoint, libs):
        context = self.tool.RunContext(self.tmp.name, "b1-ckpt")
        return self.tool.LocalBackend(self._reader(checkpoint), context, libs=libs)

    def test_checkpoint_choice_by_mode(self):
        self.assertEqual(self.tool.resolve_checkpoint("final"), "tuned")
        self.assertEqual(self.tool.resolve_checkpoint("final", "base"), "base")
        self.assertEqual(self.tool.resolve_checkpoint("base"), "base")
        for mode, name in (("base", "tuned"), ("final", "other")):
            with self.assertRaises(ValueError, msg=mode + " " + name):
                self.tool.resolve_checkpoint(mode, name)
        self.assertEqual(self._reader("base")["checkpoint"], "base")
        self.assertEqual(self._reader(None)["checkpoint"], "tuned")

    def test_base_never_applies_the_adapter(self):
        libs = _FakeLibs()
        resident = mock.patch.object(self.fm, "resident", side_effect=AssertionError("tuned loader"))
        with self._mocked(libs, verify_adapter=False), resident:
            backend = self._backend("base", libs)
            loaded = backend.prepare()
        self.assertEqual(libs.calls["adapter"], [], "the base checkpoint applied an adapter")
        self.assertEqual((libs.calls["model"], libs.calls["kbit"]), ([str(self.base)], 1))
        self.assertEqual(libs.calls["attention"], ["eager"], "the base loads with the producer's attention (D-060)")
        record = loaded["checkpoint"]
        self.assertEqual((record["checkpoint"], record["adapter_applied"], record["adapter_sha256"]),
                         ("base", False, None))
        weights = self.spec["base_hashes"]["model.safetensors"]
        self.assertEqual(loaded["digest"], "rev-fixture:" + weights)
        self.assertEqual(record["model_safetensors_sha256"], weights)
        self.assertTrue(backend._mdl.config.use_cache)

    def test_tuned_applies_the_adapter(self):
        libs = _FakeLibs()
        with self._mocked(libs):
            loaded = self._backend("tuned", libs).prepare()
        self.assertEqual([Path(p) for p in libs.calls["adapter"]], [self.adapter_dir],
                         "the tuned checkpoint did not apply its adapter")
        self.assertEqual(libs.calls["model"], [str(self.base)])
        self.assertEqual(libs.calls["attention"], ["eager"], "the tuned producer loads eager (D-060)")
        self.assertEqual(loaded["checkpoint"]["adapter_applied"], True)
        self.assertEqual(loaded["digest"], "rev-fixture:%s+adapter:%s" % (
            self.spec["base_hashes"]["model.safetensors"], "a" * 64))

    def test_base_hash_mismatch_refuses(self):
        (self.base / "model.safetensors").write_text("other weights", encoding="utf-8")
        for checkpoint in ("base", "tuned"):
            libs = _FakeLibs()
            with self._mocked(libs, verify_adapter=checkpoint == "tuned"):
                with self.assertRaisesRegex(RuntimeError, "Base asset mismatch", msg=checkpoint):
                    self._backend(checkpoint, libs).prepare()
            self.assertEqual((libs.calls["model"], libs.calls["adapter"]), ([], []), checkpoint)

    def test_entry_records_the_checkpoint(self):
        # run_b1, the in-process entry, resolves the reader with the checkpoint and records it
        replies = json.loads(REPLIES.read_text(encoding="utf-8"))["replies"]
        for checkpoint in ("base", "tuned"):
            identity = dict(EXPECTED, checkpoint={"checkpoint": checkpoint})
            with tempfile.TemporaryDirectory(prefix="b1_entry_") as tmp, \
                    mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "final"}):
                summary = self.tool.run_b1(BUNDLE, ITEMS, Path(tmp) / checkpoint, checkpoint,
                                           expected=EXPECTED, max_new_tokens=64,
                                           backend=FakeBackend(replies, identity=identity))
                label = json.loads(next((Path(tmp) / checkpoint / "labels").glob("*.json"))
                                   .read_text(encoding="utf-8"))
            self.assertEqual((summary["reader"]["checkpoint"], summary["checkpoint"]["checkpoint"],
                              label["checkpoint"]), (checkpoint, checkpoint, checkpoint))


def _torch_or_skip(case):
    """torch for the attention cases (imported, never a model loaded); skipped with the
    reason where it is not installed."""
    try:
        import torch
        from torch.nn.attention import SDPBackend, sdpa_kernel  # noqa: F401
    except ImportError as exc:
        case.skipTest("torch with torch.nn.attention is not installed here: " + str(exc))
    return torch


def _enabled_backends(torch):
    """The sdpa backends torch allows right now, read here, not through the tool."""
    flags = {"CUDNN_ATTENTION": torch.backends.cuda.cudnn_sdp_enabled(),
             "EFFICIENT_ATTENTION": torch.backends.cuda.mem_efficient_sdp_enabled(),
             "FLASH_ATTENTION": torch.backends.cuda.flash_sdp_enabled(),
             "MATH": torch.backends.cuda.math_sdp_enabled()}
    return "+".join(name for name, on in sorted(flags.items()) if on)


class _Batch(dict):
    def to(self, device):
        return self


class _AttentionTokenizer:
    """A tokenizer stand-in: one id per word, a fixed decoded reply."""
    chat_template = "fixture"

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        return "\n".join(m["content"] for m in messages)

    def __call__(self, text, return_tensors=None, add_special_tokens=True):
        ids = list(range(1, len(text.split()) + 1))
        if return_tensors == "pt":
            import torch
            return _Batch(input_ids=torch.tensor([ids]), attention_mask=torch.ones((1, len(ids)), dtype=torch.long))
        return {"input_ids": ids}

    def decode(self, ids, skip_special_tokens=True):
        return '{"label": "fixture"}'


class _AttentionModel:
    """The shared resident model, mocked: its config carries `_attn_implementation` (eager,
    as scripts/final_models.py loads the producer, D-060), it sits on a CUDA device
    (a name only: nothing is moved there), and generate() records the attention setting and
    the enabled sdpa backends at the moment it is called. `fail` is raised by generate."""

    def __init__(self):
        self.config = SimpleNamespace(_attn_implementation="eager", max_position_embeddings=10 ** 6,
                                      model_type="qwen2")
        self.device, self.calls, self.fail = "cuda:0", [], None
        self.generation_config = SimpleNamespace(eos_token_id=None)
        self._shimmer_identity = {"model_mode": "final", "adapter_checkpoint": 168}

    def generate(self, input_ids=None, attention_mask=None, max_new_tokens=1, **kwargs):
        import torch
        self.calls.append((self.config._attn_implementation, _enabled_backends(torch)))
        if self.fail is not None:
            raise self.fail
        return torch.cat([input_ids, torch.tensor([[7, 7]])], dim=1)


class AttentionChecks(unittest.TestCase):
    """D-056 conditions 1 to 4 as D-060 and D-061 amend them, on mocked models (no model load)
    and a tiny randomly built CPU model (no download): B1 runs eager with chunked prefill (E),
    and so does B3 on the same resident model in the same process (until D-058 this check held
    B3 eager; D-058 held both sdpa; D-060 returned both to eager, B1 following the producer);
    the attention and prefill are recorded in every reply record and the summary and checked
    against what each call observed; an out-of-memory error or a refused kernel stops B1 as a
    setup failure, never an abstention; one-shot prefill only with a recorded decision; and the
    one shared generate helper gives one-shot prefill's greedy output and next-token scores."""

    def setUp(self):
        if _absent():
            self.skipTest(ABSENT_REASON)
        self.tool = _load("bare_model")
        self.fm = self.tool.final_models
        self.tmp = tempfile.TemporaryDirectory(prefix="b1_attn_")
        self.spec = {"checkpoint": 168, "model_id": "fixture/base-4bit", "revision": "rev-fixture",
                     "base_hashes": {"model.safetensors": "c" * 64},
                     "files": {"adapter": {"path": "x", "sha256": "a" * 64}}}

    def tearDown(self):
        self.tmp.cleanup()

    @contextlib.contextmanager
    def _resident(self, model):
        """The tuned producer resident in final_models' cache, as the pipeline leaves it."""
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "final"}))
            stack.enter_context(mock.patch.dict(self.fm._RESIDENTS, {"final-producer": (_AttentionTokenizer(), model)},
                                                clear=True))
            stack.enter_context(mock.patch.object(self.fm, "verify_runtime", return_value=None))
            stack.enter_context(mock.patch.object(self.fm, "specification", return_value=self.spec))
            stack.enter_context(mock.patch.object(self.fm, "load", side_effect=AssertionError("a model load")))
            yield

    def _b3_call(self):
        """One B3 call as the pipeline makes it: agent_wrapper.AgentWrapper.call_local on the
        resident tuned producer (final mode), with its cost and reply writers stubbed. Returns
        the attention its reply record would carry."""
        import agent_wrapper
        caller = object.__new__(agent_wrapper.AgentWrapper)
        written = []
        caller.backend, caller.model, caller.run_context = "local_producer", self.spec["model_id"], None
        caller.name, caller._optimized_semantics = "PROCESSOR", False
        caller._record_cost = lambda r, **kw: None
        caller._write_reply = lambda r, sent: written.append(dict(sent))
        result = caller.call_local("a fixture prompt", max_new_tokens=2)
        self.assertTrue(result.ok, result.error)
        return written[-1]["attention"]

    def test_b1_and_b3_run_eager_chunked_in_one_process(self):
        """D-060 and D-061 (amending D-056 condition 2 and D-058): the resident producer is
        eager, B3's call runs unpinned under the sealed chunked prefill and records both, B1's
        calls likewise (B1 follows the producer), and the resident model is eager after B1,
        whatever a B1 call raised."""
        torch = _torch_or_skip(self)
        import reply_records
        self.assertEqual((self.tool.B3_ATTENTION, self.tool.B1_ATTENTION), ("eager", "eager"))
        model = _AttentionModel()
        everything = _enabled_backends(torch)
        b3_record = {"attention_implementation": "eager", "sdpa_backend": None,
                     "attention_decision": None, "pinned": False,
                     "prefill": "chunked", "prefill_chunk_tokens": 512, "prefill_decision": "D-061"}
        with self._resident(model):
            self.assertEqual(self._b3_call(), b3_record)
            with mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "final"}):
                reader = self.tool.resolve_reader(ROOT, max_new_tokens=8, checkpoint="tuned")
            context = self.tool.RunContext(Path(self.tmp.name) / "b1", "b1-attn")
            backend = self.tool.LocalBackend(reader, context)
            out = Path(self.tmp.name) / "b1"
            summary = self.tool.run(BUNDLE, ITEMS, out, backend=backend, reader=reader, development=True)
            self._b3_call()
            # a B1 call that raises still hands the model back eager
            model.fail = RuntimeError("fixture failure inside generate")
            with self.assertRaises(RuntimeError):
                backend.generate("s", "u", 2)
            model.fail = None
            self.assertEqual(self._b3_call(), b3_record)
        unpinned = ("eager", everything)
        self.assertNotEqual(everything, "EFFICIENT_ATTENTION", "every backend is enabled outside a call")
        self.assertEqual(_enabled_backends(torch), everything, "nothing is pinned for eager")
        self.assertEqual(model.calls, [unpinned] * 8)
        self.assertEqual(model.config._attn_implementation, "eager", "the resident model is eager after B1")
        records = reply_records.records(out / "audit" / "model_replies")
        self.assertEqual(len(records), 4)
        for record in records:
            self.assertEqual({k: record["attention"][k] for k in B1_ATTENTION}, B1_ATTENTION)
            # what the prefill measured: the fixture prompts fit one chunk, so generate()
            # prefilled them itself; a mocked model has no forward hook, so no seconds
            self.assertEqual({k: record["prefill"][k] for k in ("chunks", "chunked_tokens", "prefill_seconds")},
                             {"chunks": 0, "chunked_tokens": 0, "prefill_seconds": None})
        self.assertEqual(summary["attention"], B1_ATTENTION)
        self.assertEqual(summary["loaded"]["attention"], B1_ATTENTION)
        self.assertEqual({k: summary["prefill_time"][k] for k in ("items", "calls_measured", "calls_chunked",
                                                                  "seconds_measured", "seconds_total")},
                         {"items": 4, "calls_measured": 4, "calls_chunked": 0, "seconds_measured": 0,
                          "seconds_total": None})

    def test_out_of_memory_stops_b1_as_a_setup_failure(self):
        torch = _torch_or_skip(self)
        import reply_records
        replies = json.loads(REPLIES.read_text(encoding="utf-8"))["replies"]
        oom = torch.cuda.OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB (fixture)")
        refused = RuntimeError("No available kernel. Aborting execution.")
        for kind, error in (("out_of_memory", oom), ("attention_kernel_refused", refused)):
            backend = FakeBackend(replies, raise_for={"a2": error})
            out = Path(self.tmp.name) / kind
            with self.assertRaises(self.tool.SetupFailure, msg=kind) as caught:
                self.tool.run(BUNDLE, ITEMS, out, backend=backend, reader=self._reader(),
                              expected=EXPECTED)
            self.assertEqual(caught.exception.kind, kind)
            self.assertEqual(backend.asked, ["a1", "a2"], kind + ": the run stops at the failing call")
            failure = json.loads((out / self.tool.SETUP_FAILURE_FILE).read_text(encoding="utf-8"))
            self.assertEqual({k: failure[k] for k in ("kind", "item_id", "items_total", "items_before_stop",
                                                      "reply_records_written")},
                             {"kind": kind, "item_id": "a2", "items_total": 4, "items_before_stop": 1,
                              "reply_records_written": 2})
            self.assertIn("never an abstention", failure["counted_as"])
            # never an abstention: the failing item gets no label, and no summary is written
            self.assertEqual(sorted(p.stem for p in (out / "labels").glob("*.json")), ["a1"])
            self.assertFalse((out / "b1_summary.json").exists())
            records = reply_records.records(out / "audit" / "model_replies")
            self.assertEqual([(r["backend_ok"], r["error_category"]) for r in records],
                             [(True, None), (False, type(error).__name__)])
            with contextlib.redirect_stderr(io.StringIO()) as err, \
                    mock.patch.object(self.tool, "run_b1", side_effect=self.tool.SetupFailure(kind, "a2", "x")):
                code = self.tool.main(["--bundle", "b", "--items", "i", "--out", "o", "--development"])
            self.assertEqual(code, 4)
            self.assertIn("setup failure (%s)" % kind, err.getvalue())
        # an ordinary generation failure stays a failed call (ABSTAIN), as before
        self.assertIsNone(self.tool.setup_failure_kind(RuntimeError("fixture failure")))
        self.assertIsNone(self.tool.setup_failure_kind(ValueError("out of memory")))
        self.assertEqual(self.tool.setup_failure_kind(RuntimeError("CUDA error: out of memory")), "out_of_memory")
        # through the real LocalBackend, an out-of-memory generate hands the model back eager
        model = _AttentionModel()
        model.fail = oom
        with self._resident(model):
            with mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "final"}):
                reader = self.tool.resolve_reader(ROOT, max_new_tokens=8, checkpoint="tuned")
            backend = self.tool.LocalBackend(reader, self.tool.RunContext(self.tmp.name, "b1-oom"))
            out = Path(self.tmp.name) / "local_oom"
            with self.assertRaises(self.tool.SetupFailure):
                self.tool.run(BUNDLE, ITEMS, out, backend=backend, reader=reader, development=True)
        self.assertEqual(model.calls, [("eager", _enabled_backends(torch))])
        self.assertEqual(model.config._attn_implementation, "eager")

    def _reader(self):
        with mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "base"}):
            return self.tool.resolve_reader(ROOT, max_new_tokens=64)

    def test_chunked_prefill_is_on_and_one_shot_needs_a_recorded_decision(self):
        """D-061: E is the default, at 512 tokens under D-061; one-shot or another chunk size
        only with the recorded decision that asks for it."""
        self.assertEqual(self.tool.attention_record(), B1_ATTENTION)
        self.assertEqual(self._reader()["attention"], B1_ATTENTION)
        for chunk, decision in (("one_shot", None), (256, None), (None, "D-056"), (512, "D-099"),
                                (256, "decided"), (0, "D-099"), ("half", "D-099"), (-1, "D-099")):
            with self.assertRaises(ValueError, msg=(chunk, decision)):
                self.tool.attention_record(chunk, decision)
        self.assertEqual(self.tool.attention_record(512, "D-061"), B1_ATTENTION)
        self.assertEqual(self.tool.attention_record("one_shot", "D-061"), B1_ONE_SHOT)
        other = self.tool.attention_record("256", "D-099")
        self.assertEqual((other["prefill"], other["prefill_chunk_tokens"], other["prefill_decision"]),
                         ("chunked", 256, "D-099"))
        parsed = self.tool.build_parser().parse_args(["--bundle", "b", "--items", "i", "--out", "o"])
        self.assertEqual((parsed.prefill_chunk, parsed.prefill_decision), (None, None))
        # the backend hands its pass's prefill to the one shared generate helper (the mocked
        # model's 7-token prompt fits one chunk plus the tail, so nothing is chunked here; the
        # tiny CPU model below runs the chunks)
        torch = _torch_or_skip(self)
        for chunk, decision in ((None, None), ("one_shot", "D-061"), (8, "D-099")):
            model = _AttentionModel()
            with self._resident(model), mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "final"}):
                reader = self.tool.resolve_reader(ROOT, max_new_tokens=8, checkpoint="tuned",
                                                  prefill_chunk=chunk, prefill_decision=decision)
                backend = self.tool.LocalBackend(reader, self.tool.RunContext(self.tmp.name, "b1-chunk"))
                backend.prepare()
                seen = []
                real = self.fm.generate_with_prefill

                def spy(mdl, inputs, **kw):
                    seen.append(dict(kw["prefill"]))
                    return real(mdl, inputs, **kw)
                with mock.patch.object(self.fm, "generate_with_prefill", spy):
                    result = backend.generate("a b c", "d e f g", 2)
            self.assertEqual(seen, [self.tool.prefill_of(reader["attention"])])
            self.assertEqual(result["attention"]["prefill_chunk_tokens"], reader["attention"]["prefill_chunk_tokens"])
        del torch

    def test_chunked_prefill_matches_one_shot_on_a_tiny_cpu_model(self):
        """D-061 items 3 and 6: the one shared helper, at the sealed 512-token chunk, on a
        prompt of three full chunks and the 2-token tail (1,538 tokens), gives one-shot
        prefill's greedy output and its next-token scores within tolerance on a tiny randomly
        built CPU Qwen2 (2 layers, no download); a prompt of one chunk plus the tail or less is
        prefilled by generate() itself."""
        torch = _torch_or_skip(self)
        try:
            from transformers import Qwen2Config, Qwen2ForCausalLM
        except ImportError as exc:
            self.skipTest("transformers' Qwen2 classes are not installed here: " + str(exc))
        torch.manual_seed(0)
        config = Qwen2Config(vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                             num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=2048,
                             sliding_window=None, use_sliding_window=False, eos_token_id=63,
                             pad_token_id=0, attn_implementation="eager")
        model = Qwen2ForCausalLM(config).eval()
        greedy = {"do_sample": False, "num_beams": 1}
        scores = {"output_scores": True, "return_dict_in_generate": True}
        e, one_shot = self.fm.prefill_setting(), self.fm.prefill_setting("one_shot", "D-061")
        long_ids = torch.randint(1, 60, (1, 3 * 512 + 2), generator=torch.Generator().manual_seed(2))
        long_inputs = {"input_ids": long_ids, "attention_mask": torch.ones_like(long_ids)}
        with torch.no_grad():
            reference, measured_one = self.fm.generate_with_prefill(
                model, long_inputs, max_new_tokens=6, decoding_kwargs=greedy, prefill=one_shot, **scores)
            chunked_out, measured_e = self.fm.generate_with_prefill(
                model, long_inputs, max_new_tokens=6, decoding_kwargs=greedy, prefill=e, **scores)
            cache, chunks = self.fm.chunked_prefill(model, long_ids, 512)
        self.assertEqual((chunks, cache.get_seq_length()), (3, 3 * 512), "two tokens are left to generate()")
        self.assertEqual({k: measured_e[k] for k in ("prompt_tokens", "chunks", "chunked_tokens", "tail_tokens")},
                         {"prompt_tokens": 1538, "chunks": 3, "chunked_tokens": 1536, "tail_tokens": 2})
        self.assertEqual((measured_one["chunks"], measured_one["tail_tokens"]), (0, 1538))
        for measured in (measured_e, measured_one):
            self.assertIsInstance(measured["prefill_seconds"], float)
        self.assertTrue(torch.equal(reference.sequences, chunked_out.sequences), "chunked greedy output differs")
        self.assertEqual(len(reference.scores), len(chunked_out.scores))
        for a, b in zip(reference.scores, chunked_out.scores):
            self.assertTrue(torch.allclose(a, b, atol=1e-4, rtol=1e-4), float((a - b).abs().max()))
        ids = torch.randint(1, 60, (1, 17), generator=torch.Generator().manual_seed(1))
        inputs = {"input_ids": ids, "attention_mask": torch.ones_like(ids)}
        real_sdpa = torch.nn.functional.scaled_dot_product_attention
        counted = []

        def counting_sdpa(*args, **kwargs):
            counted.append(1)
            return real_sdpa(*args, **kwargs)

        calls = []
        hook = model.register_forward_pre_hook(lambda module, args: calls.append(1))
        try:
            with torch.no_grad(), mock.patch.object(torch.nn.functional, "scaled_dot_product_attention",
                                                    counting_sdpa):
                # an sdpa measurement pass on the CPU, which has no memory-efficient kernel:
                # pinned to it, the call is refused (raises), never run on another kernel; the
                # model is eager again after
                with self.assertRaises(RuntimeError) as refused:
                    with self.tool.b1_attention(model, implementation="sdpa"):
                        model(**inputs)
                self.assertEqual(self.tool.setup_failure_kind(refused.exception), "attention_kernel_refused")
                self.assertEqual(model.config._attn_implementation, "eager")
                counted.clear()
                # B1's own pass: eager, chunked through the shared helper (17 tokens in chunks of 5)
                with self.tool.b1_attention(model):
                    calls.clear()
                    eager, short = self.fm.generate_with_prefill(model, inputs, max_new_tokens=4, decoding_kwargs=greedy,
                                                                 prefill=self.fm.prefill_setting(5, "D-099"), **scores)
                self.assertEqual(counted, [], "eager attention called sdpa")
                self.assertEqual((short["chunks"], short["tail_tokens"]), (3, 2))
                self.assertEqual(len(calls), 3 + 4, "three chunks, then one forward per generated token")
                # the same switch, sdpa on the CPU's math kernel, one shot
                with self.tool.b1_attention(model, backends=("MATH",), implementation="sdpa"):
                    one, _ = self.fm.generate_with_prefill(model, inputs, max_new_tokens=4, decoding_kwargs=greedy,
                                                           prefill=one_shot, **scores)
                    self.assertGreater(len(counted), 0, "the switch did not reach the attention code")
        finally:
            hook.remove()
        self.assertEqual(model.config._attn_implementation, "eager")
        # and sdpa gives the eager kernel's answer on this model
        self.assertTrue(torch.equal(eager.sequences, one.sequences))
        for a, b in zip(one.scores, eager.scores):
            self.assertTrue(torch.allclose(a, b, atol=1e-4, rtol=1e-4), float((a - b).abs().max()))


GIB = 2 ** 30


class _FakeCuda:
    """torch.cuda's peak-memory counters, mocked (no device touched): `events` records each
    reset, read and generate in order; bump() is what a generate call allocates."""

    def __init__(self, available=True, initialized=True):
        self.available, self.initialized = available, initialized
        self.events, self.allocated, self.peak, self.reserved = [], 5 * GIB, 0, 0

    def is_available(self):
        return self.available

    def is_initialized(self):
        return self.initialized

    def reset_peak_memory_stats(self):
        self.events.append("reset")
        self.peak, self.reserved = self.allocated, self.allocated + GIB

    def memory_allocated(self):
        return self.allocated

    def max_memory_allocated(self):
        self.events.append("read")
        return self.peak

    def max_memory_reserved(self):
        return self.reserved

    def empty_cache(self):
        self.events.append("empty_cache")

    def bump(self, size):
        self.peak = max(self.peak, self.allocated + size)
        self.reserved = max(self.reserved, self.allocated + size + GIB)


class _MeasuredBackend(FakeBackend):
    """The mocked model on a mocked CUDA device: each call allocates one more GiB than the last."""

    def __init__(self, replies, cuda, **kwargs):
        super().__init__(replies, **kwargs)
        self.cuda = cuda

    def generate(self, system, user, max_new_tokens):
        self.cuda.events.append("generate")
        self.cuda.bump(GIB * (len(self.asked) + 1))
        return super().generate(system, user, max_new_tokens)


class MeasurementChecks(unittest.TestCase):
    """D-056 condition 6 on mocked models (no model load, no device touched): an eager
    measurement pass is accepted only with its recorded decision and runs eager, recorded in
    every reply record, label and the summary; each pass's peak GPU memory (allocated and
    reserved) is reset after the load and read after the last item, null without CUDA, and a
    model the pass loaded is released when it ends; two pass folders are compared item by item
    for byte-identical replies and agreeing labels, counts only."""

    _resident = AttentionChecks._resident

    def setUp(self):
        if _absent():
            self.skipTest(ABSENT_REASON)
        self.tool = _load("bare_model")
        self.fm = self.tool.final_models
        self.tmp = tempfile.TemporaryDirectory(prefix="b1_measure_")
        self.spec = {"checkpoint": 168, "model_id": "fixture/base-4bit", "revision": "rev-fixture",
                     "base_hashes": {"model.safetensors": "c" * 64},
                     "files": {"adapter": {"path": "x", "sha256": "a" * 64}}}
        self.replies = json.loads(REPLIES.read_text(encoding="utf-8"))["replies"]

    def tearDown(self):
        self.tmp.cleanup()

    def _reader(self, **kwargs):
        with mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "base"}):
            return self.tool.resolve_reader(ROOT, max_new_tokens=64, **kwargs)

    def test_sdpa_measurement_pass_needs_its_decision_and_is_recorded(self):
        """D-056 condition 6 as D-060 and D-061 amend it: the run proper is eager; an sdpa
        measurement pass only with its recorded decision, pinned to the memory-efficient
        backend for its calls, recorded everywhere, and the resident model eager again after."""
        for attention, decision in (("sdpa", None), ("eager", "D-061"), ("sdpa", "decided"), ("flash", None)):
            with self.assertRaises(ValueError, msg=(attention, decision)):
                self.tool.attention_record(attention=attention, attention_decision=decision)
        self.assertEqual(self.tool.attention_record(attention="sdpa", attention_decision="D-061"), B1_SDPA)
        parsed = self.tool.build_parser().parse_args(["--bundle", "b", "--items", "i", "--out", "o"])
        self.assertEqual((parsed.attention, parsed.attention_decision), ("eager", None))
        out = Path(self.tmp.name) / "refused"
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = self.tool.main(["--bundle", str(BUNDLE), "--items", str(ITEMS), "--out", str(out),
                                   "--attention", "sdpa", "--development"])
        self.assertEqual(code, 4)
        self.assertIn("--attention-decision", err.getvalue())
        self.assertFalse(out.exists(), "a refused sdpa pass wrote something")
        # the sdpa pass on the shared resident model (eager, D-060): sdpa pinned for every
        # call, recorded in every reply record, label and the summary; the resident model is
        # eager again afterwards and B3's next call runs eager, unpinned
        torch = _torch_or_skip(self)
        import reply_records
        model = _AttentionModel()
        out = Path(self.tmp.name) / "tuned_sdpa"
        with self._resident(model):
            with mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "final"}):
                reader = self.tool.resolve_reader(ROOT, max_new_tokens=8, checkpoint="tuned",
                                                  attention="sdpa", attention_decision="D-061")
            backend = self.tool.LocalBackend(reader, self.tool.RunContext(out, "b1-sdpa"))
            summary = self.tool.run(BUNDLE, ITEMS, out, backend=backend, reader=reader, development=True)
            self.assertEqual(model.config._attn_implementation, "eager", "the sdpa pass restores eager")
            self.assertEqual(AttentionChecks._b3_call(self)["attention_implementation"], "eager")
        everything = _enabled_backends(torch)
        self.assertEqual(model.calls, [("sdpa", "EFFICIENT_ATTENTION")] * 4 + [("eager", everything)])
        self.assertEqual(model.config._attn_implementation, "eager")
        records = reply_records.records(out / "audit" / "model_replies")
        self.assertEqual([r["attention"] for r in records], [B1_SDPA] * 4)
        labels = [json.loads(p.read_text(encoding="utf-8")) for p in (out / "labels").glob("*.json")]
        self.assertEqual([l["attention"] for l in labels], [B1_SDPA] * 4)
        self.assertEqual((summary["attention"], summary["loaded"]["attention"]), (B1_SDPA, B1_SDPA))

    def test_peak_gpu_memory_is_measured_per_pass_and_null_without_cuda(self):
        cuda = _FakeCuda()
        out = Path(self.tmp.name) / "measured"
        with mock.patch.dict(sys.modules, {"torch": SimpleNamespace(cuda=cuda)}):
            summary = self.tool.run(BUNDLE, ITEMS, out, backend=_MeasuredBackend(self.replies, cuda),
                                    reader=self._reader(), expected=EXPECTED)
        # reset once after the load and before the first item, read after the last
        self.assertEqual([e for e in cuda.events if e != "read"], ["reset"] + ["generate"] * 4)
        self.assertEqual(cuda.events[-1], "read")
        memory = summary["gpu_memory"]
        self.assertEqual((memory["peak_allocated_bytes"], memory["peak_reserved_bytes"],
                          memory["allocated_at_start_bytes"], memory["measured"]),
                         (9 * GIB, 10 * GIB, 5 * GIB, True))
        written = json.loads((out / "b1_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(written["gpu_memory"], memory)
        # no CUDA, CUDA not in use, or no torch at all: every value null
        nulls = {"peak_allocated_bytes": None, "peak_reserved_bytes": None, "allocated_at_start_bytes": None,
                 "measured": False}
        for name, modules in (("cpu", {"torch": SimpleNamespace(cuda=_FakeCuda(available=False))}),
                              ("idle", {"torch": SimpleNamespace(cuda=_FakeCuda(initialized=False))}),
                              ("absent", {"torch": None})):
            with mock.patch.dict(sys.modules, modules):
                summary = self.tool.run(BUNDLE, ITEMS, Path(self.tmp.name) / name, backend=FakeBackend(self.replies),
                                        reader=self._reader(), expected=EXPECTED)
            self.assertEqual({k: summary["gpu_memory"][k] for k in nulls}, nulls, name)
        # a call that stops the run records the peak so far in b1_setup_failure.json
        cuda = _FakeCuda()
        stopped = Path(self.tmp.name) / "stopped"
        with mock.patch.dict(sys.modules, {"torch": SimpleNamespace(cuda=cuda)}):
            with self.assertRaises(self.tool.SetupFailure):
                self.tool.run(BUNDLE, ITEMS, stopped, reader=self._reader(), expected=EXPECTED,
                              backend=_MeasuredBackend(self.replies, cuda, raise_for={
                                  "a2": RuntimeError("CUDA error: out of memory")}))
        failure = json.loads((stopped / self.tool.SETUP_FAILURE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(failure["gpu_memory"]["peak_allocated_bytes"], 7 * GIB)

    def test_a_model_the_pass_loaded_is_released_when_it_ends(self):
        released = []
        replies = self.replies

        class Built(FakeBackend):
            def __init__(self, reader, context, identity=None):
                super().__init__(replies, identity=identity)

            def release(self):
                released.append(1)
        with mock.patch.object(self.tool, "LocalBackend", Built):
            self.tool.run(BUNDLE, ITEMS, Path(self.tmp.name) / "built", reader=self._reader(), expected=EXPECTED)
            self.assertEqual(released, [1])
            with mock.patch.object(self.tool, "LocalBackend",
                                   lambda reader, context: Built(reader, context, dict(EXPECTED, digest="other"))):
                with self.assertRaises(self.tool.SetupError):
                    self.tool.run(BUNDLE, ITEMS, Path(self.tmp.name) / "refused", reader=self._reader(),
                                  expected=EXPECTED)
            self.assertEqual(released, [1, 1], "a pass that stops still releases its model")
        # a backend handed in is the caller's: never released by the run
        handed = Built(None, None)
        self.tool.run(BUNDLE, ITEMS, Path(self.tmp.name) / "handed", backend=handed, reader=self._reader(),
                      expected=EXPECTED)
        self.assertEqual(released, [1, 1])
        # the real release drops the model and empties the CUDA cache
        cuda = _FakeCuda()
        backend = self.tool.LocalBackend(self._reader(), self.tool.RunContext(self.tmp.name, "b1-release"))
        backend._tok, backend._mdl = object(), object()
        with mock.patch.dict(sys.modules, {"torch": SimpleNamespace(cuda=cuda)}):
            backend.release()
        self.assertEqual((backend._tok, backend._mdl, cuda.events), (None, None, ["empty_cache"]))

    def _pass(self, name, replies, **kwargs):
        out = Path(self.tmp.name) / name
        self.tool.run(BUNDLE, ITEMS, out, backend=FakeBackend(replies), reader=self._reader(),
                      expected=EXPECTED, **kwargs)
        return out

    def test_two_passes_are_compared_for_byte_identical_replies_and_agreeing_labels(self):
        import copy
        a = self._pass("tuned", self.replies)
        b = self._pass("tuned_repeat", self.replies)
        hashed = self._pass("tuned_hashed", self.replies, sensitive=True)
        changed = copy.deepcopy(self.replies)
        changed["a1"]["reply"] += " "                       # one byte more, the same label
        changed["a3"]["reply"] = "No label this time."      # another reply, and an abstention
        c = self._pass("tuned_eager", changed)
        out = Path(self.tmp.name) / "compare"
        same = self.tool.compare_passes(a, b, out / "same.json")["counts"]
        self.assertEqual({k: same[k] for k in ("items", "in_both", "replies_compared", "replies_byte_identical",
                                               "replies_differ", "reply_missing", "labels_agree", "labels_differ",
                                               "both_abstained")},
                         {"items": 4, "in_both": 4, "replies_compared": 3, "replies_byte_identical": 3,
                          "replies_differ": 0, "reply_missing": 1, "labels_agree": 4, "labels_differ": 0,
                          "both_abstained": 2})
        # a sensitive pass keeps only hashes, and is compared on them
        self.assertEqual(self.tool.compare_passes(a, hashed, out / "hashed.json")["counts"]["replies_byte_identical"], 3)
        result = self.tool.compare_passes(a, c, out / "changed.json")
        self.assertEqual({k: result["counts"][k] for k in ("replies_byte_identical", "replies_differ",
                                                           "labels_agree", "labels_differ", "both_abstained")},
                         {"replies_byte_identical": 1, "replies_differ": 2, "labels_agree": 3, "labels_differ": 1,
                          "both_abstained": 2})
        self.assertEqual({r["item_id"]: (r["reply_byte_identical"], r["label_agrees"]) for r in result["items"]},
                         {"a1": (False, True), "a2": (True, True), "a3": (False, False), "a4": (None, True)})
        self.assertEqual((result["a"]["folder"], result["b"]["folder"]), ("tuned", "tuned_eager"))
        # an item missing on one side is counted, never compared
        (c / "labels" / "a2.json").unlink()
        missing = self.tool.compare_passes(a, c, out / "missing.json")["counts"]
        self.assertEqual((missing["items"], missing["in_both"], missing["missing_in_b"]), (4, 3, 1))
        # the command: counts only in its output, never a reply's text or a label
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.tool.main(["compare", "--a", str(a), "--b", str(c), "--out", str(out / "cli.json")])
        self.assertEqual(code, 0)
        text = (out / "cli.json").read_text(encoding="utf-8")
        for secret in ("Line total", "refuted", "not enough info", "No label this time"):
            self.assertNotIn(secret, text)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.tool.main(["compare", "--a", str(a), "--b", str(out / "none"),
                                             "--out", str(out / "x.json")]), 4)


def _attention_ignoring_sdpa(original):
    """B1's switch always to eager, whatever the pass declared."""
    def switch(model, backends=None, implementation="eager"):
        return original(model, backends)
    return switch


def _attention_record_without_its_decision(original):
    """The declared attention built without the rule that sdpa needs its decision."""
    def record(prefill_chunk=None, prefill_decision=None, attention="eager", attention_decision=None):
        return dict(original(prefill_chunk, prefill_decision), attention_implementation=attention,
                    sdpa_backend="EFFICIENT_ATTENTION" if attention == "sdpa" else None,
                    attention_decision=attention_decision)
    return record


def _prefill_without_its_decision(original):
    """The prefill rule without its decision: one-shot or any chunk size taken as asked."""
    def setting(chunk=None, decision=None):
        if chunk == "one_shot":
            return {"prefill": "one_shot", "prefill_chunk_tokens": None, "prefill_decision": decision}
        return original(None if decision is None else chunk, decision)
    return setting


def _prefill_leaving_one_token(original):
    """Chunked prefill that leaves one prompt token to generate(), not two (D-061 item 3)."""
    def prefill(model, input_ids, chunk_tokens, *, cache=None):
        import torch
        return original(model, torch.cat([input_ids, input_ids[:, -1:]], dim=1), chunk_tokens, cache=cache)
    return prefill


def _attention_without_restore(original):
    """B1's switch that leaves the resident model on the pass's attention when it ends."""
    def switch(model, backends=None, implementation="eager"):
        inner = original(model, backends, implementation)

        @contextlib.contextmanager
        def kept():
            with inner as observe:
                yield observe
            for config in {id(c): c for c in [model.config]}.values():
                config._attn_implementation = implementation
        return kept()
    return switch


def _pin_that_pins_nothing(original):
    """B3's per-call pin that records the memory-efficient backend but never pins it."""
    @contextlib.contextmanager
    def pin(model, decision=None):
        yield {"attention_implementation": getattr(model.config, "_attn_implementation", None),
               "sdpa_backend": "EFFICIENT_ATTENTION", "attention_decision": decision, "pinned": True}
    return pin


# Neutralize, fail, restore, pass (D-056 condition 6; D-058, D-060 and D-061 for the amended
# attention and prefill checks): each entry names a check, the function it holds (in
# bare_model.py unless a module is named fifth), and a mutant built from the original;
# prove_neutralizations() runs the check, then with the mutant in place (it must fail and the
# mutant must have been called), then restored.
# `py -3.12 -X utf8 scripts/baseline_checks.py --prove`.
NEUTRALIZATIONS = [
    (AttentionChecks, "test_b1_and_b3_run_eager_chunked_in_one_process", "pinned_attention",
     _pin_that_pins_nothing, "final_models"),
    (AttentionChecks, "test_b1_and_b3_run_eager_chunked_in_one_process", "producer_prefill",
     lambda original: (lambda environ=None: dict(original(environ), prefill="one_shot", prefill_chunk_tokens=None)),
     "final_models"),
    (AttentionChecks, "test_chunked_prefill_is_on_and_one_shot_needs_a_recorded_decision", "prefill_setting",
     _prefill_without_its_decision, "final_models"),
    (AttentionChecks, "test_chunked_prefill_matches_one_shot_on_a_tiny_cpu_model", "chunked_prefill",
     _prefill_leaving_one_token, "final_models"),
    (CheckpointChecks, "test_tuned_applies_the_adapter", "load_attention",
     lambda original: (lambda role, spec=None: "sdpa"), "final_models"),
    (AttentionChecks, "test_out_of_memory_stops_b1_as_a_setup_failure", "setup_failure_kind",
     lambda original: (lambda exc: None)),
    (MeasurementChecks, "test_sdpa_measurement_pass_needs_its_decision_and_is_recorded", "b1_attention",
     _attention_without_restore),
    (MeasurementChecks, "test_sdpa_measurement_pass_needs_its_decision_and_is_recorded", "b1_attention",
     _attention_ignoring_sdpa),
    (MeasurementChecks, "test_sdpa_measurement_pass_needs_its_decision_and_is_recorded", "attention_record",
     _attention_record_without_its_decision),
    (MeasurementChecks, "test_peak_gpu_memory_is_measured_per_pass_and_null_without_cuda", "start_gpu_memory",
     lambda original: (lambda: (None, None))),
    (MeasurementChecks, "test_peak_gpu_memory_is_measured_per_pass_and_null_without_cuda", "gpu_memory_probe",
     lambda original: (lambda: getattr(sys.modules.get("torch"), "cuda", None))),
    (MeasurementChecks, "test_two_passes_are_compared_for_byte_identical_replies_and_agreeing_labels",
     "reply_identity", lambda original: (lambda record: "same")),
]


def prove_neutralizations():
    """{passed, proofs}: every NEUTRALIZATIONS entry passes, fails with its mutant in place
    (which was called), and passes again restored."""
    module = sys.modules[__name__]
    loader = module._load
    proofs = []

    def single(case, name):
        result = unittest.TestResult()
        case(name).run(result)
        return result.wasSuccessful() and not result.skipped

    for entry in NEUTRALIZATIONS:
        case, name, attribute, mutant = entry[:4]
        owner = entry[4] if len(entry) > 4 else "bare_model"
        invocations = []

        def counting(original, _mutant=mutant):
            replacement = _mutant(original)

            def counted(*args, **kwargs):
                invocations.append(1)
                return replacement(*args, **kwargs)
            return counted

        def mutated(module_name, _attribute=attribute):
            tool = loader(module_name)
            if module_name == "bare_model" and owner == "bare_model":
                setattr(tool, _attribute, counting(getattr(tool, _attribute)))
            return tool
        before = single(case, name)
        if owner == "bare_model":
            with mock.patch.object(module, "_load", mutated):
                failed = not single(case, name)
        else:
            import importlib
            shared = importlib.import_module(owner)
            with mock.patch.object(shared, attribute, counting(getattr(shared, attribute))):
                failed = not single(case, name)
        after = single(case, name)
        proofs.append({"check": name, "neutralized": owner + "." + attribute, "baseline_pass": before,
                       "neutralized_fail": failed and bool(invocations), "restored_pass": after,
                       "mutated_branch_invocations": len(invocations)})
    passed = all(p["baseline_pass"] and p["neutralized_fail"] and p["restored_pass"] for p in proofs)
    return {"passed": passed, "proofs": proofs}


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
    return _verdict([_run(BareModelChecks), _run(CheckpointChecks), _run(AttentionChecks),
                     _run(MeasurementChecks), _run(AbsentChecks)],
                    "B1 with a mocked backend writes exactly one reply record per item (a failed "
                    "call included) joined to one typed label by call id, asks no item of another "
                    "document, prepares and verifies its model once and stops before generating on "
                    "a load, identity, context or record failure, parses the final-line JSON label "
                    "(escape repair, UNCERTAIN) or abstains, records replies that reach the output "
                    "allowance, decides the 95 percent parse-rate floor on the rate pooled per "
                    "benchmark over every document, sends the preregistered "
                    "prompt (revision 3: the undecided invitation only where the rule asks for "
                    "UNCERTAIN) with the reference material, uses the one cut rule in "
                    "common/cut.py, and reads its model and decoding policy from the tracked "
                    "configuration; in final mode its base checkpoint (the pinned base, "
                    "base_hashes checked, no adapter) never applies the adapter, its tuned "
                    "checkpoint does, a base hash mismatch refuses before any load, and each "
                    "records its digest (mocked model); D-060 and D-061: B1 generates eager with "
                    "chunked prefill (512 tokens, D-061), as B3 does on the same resident model in "
                    "the same process, through one shared generate helper, records and verifies the "
                    "attention and prefill in every reply record and the summary, stops on an "
                    "out-of-memory error or a refused kernel as a setup failure (never an "
                    "abstention), takes one-shot prefill only with a recorded decision, and the "
                    "helper gives one-shot prefill's greedy output and next-token scores on a tiny "
                    "CPU model built in the check (three chunks and the 2-token tail); D-056 "
                    "condition 6: an sdpa measurement pass only with its recorded decision, recorded "
                    "in every reply record, label and summary, the resident model restored to eager after it, "
                    "each pass's peak GPU memory (null without "
                    "CUDA), and a comparison of two passes counting byte-identical replies and "
                    "agreeing labels")


def check():
    results = [_run(PythonOnlyChecks), _run(BareModelChecks), _run(CheckpointChecks),
               _run(AttentionChecks), _run(MeasurementChecks), _run(AbsentChecks)]
    return _verdict(results, "B2 makes no model call, imports no model library, writes the "
                             "pipeline's completion record and marks its output an ablation on each "
                             "file's first line; B1 verifies its model once and stops before "
                             "generating on any setup failure, writes one reply record per item, "
                             "parses (with escape repair) or abstains, records truncation, pools the "
                             "parse rate per benchmark for its floor, sends the preregistered prompt (revision 3) with "
                             "reference material, and uses the one cut rule and prompt renderer; "
                             "its base checkpoint never applies the adapter, its tuned one does, "
                             "and a base hash mismatch refuses (mocked model); it runs eager with "
                             "chunked prefill, as B3 does on the same resident model in the same "
                             "process (D-060, D-061), stops on out of memory as a setup failure, "
                             "and takes one-shot prefill only with a recorded decision; an sdpa "
                             "measurement pass needs its recorded decision and restores eager after it, each pass "
                             "records its peak GPU memory, and two passes are compared for "
                             "byte-identical replies and agreeing labels (D-056 condition 6)")


if __name__ == "__main__":
    if sys.argv[1:] == ["--prove"]:
        receipt = prove_neutralizations()
        print(json.dumps(receipt, indent=2))
        sys.exit(0 if receipt["passed"] else 1)
    print(check())
