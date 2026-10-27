"""Gate checks for the two baseline arms under benchmark/baselines/ (loop stage S4f).

B2 (``python_only.py``) runs Shimmer's computing layer on a synthetic bundle and
must make ZERO model calls: every backend function of AgentWrapper (call_claude,
call_gpt, call_qwen, call_local, dispatch, run_task), the classifier's predict and
the reply-record writer are replaced by mocks that fail when touched, and no model
library may be imported. It must still find the planted product mismatch, list the
plan a model would have been asked under ``ablation_not_asked``, and mark every file
it writes as an ablation on its first line or in its first key.

B1 (``bare_model.py``) runs with a mocked model backend (no model load) and must write
EXACTLY ONE reply record per item through reply_records.write, joined to the item's
typed label by call id, including the item whose call fails, and never ask an item of
another document. Its parser, its prompt (word for word against the preregistration
when that file is present), its cut rule (a fake token counter) and its reading of
the reading agent's model and decoding policy from the tracked configuration are
checked beside it.

Every case runs in a temporary directory and writes nothing under config/, durable/,
ontology/ or output/. benchmark/ is not shipped in the container image, so with
benchmark/baselines/ absent every case is SKIPPED with the reason, never failed.
"""
import contextlib
import importlib.util
import json
import os
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
        loaded_before = {m for m in MODEL_LIBRARIES if m in sys.modules}
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
                else:
                    self.assertTrue(text.splitlines()[0].startswith("ABLATION"), path.name)
            data = json.loads((out / "deliverables" / "dq4" / "review_data.json").read_text(encoding="utf-8"))
            irregular = [f for f in data["findings"] if f.get("record_verdict") == "irregular"]
            self.assertEqual([(f["relation"], f["source_rule_id"], f["value_a"], f["value_b"])
                              for f in irregular],
                             [("product_mismatch", "CONV-QA-01", 48.0, 52.0)])
            self.assertEqual(len(data["amendments"]), 1)
            pairing = json.loads((out / "audit" / "pairing_map.json").read_text(encoding="utf-8"))["dq4"]
            self.assertEqual(pairing["calls_made"], 0)
            self.assertEqual([(r["unit_id"], r["source_rule_id"], r["kind"])
                              for r in pairing["ablation_not_asked"]],
                             [("u03-p-00003", "CONV-QA-02", "uncomputable")])
        self.assertEqual({m for m in MODEL_LIBRARIES if m in sys.modules} - loaded_before, set(),
                         "B2 imported a model library")
        self.assertEqual(_config_snapshot(), config_before, "B2 changed a config file")


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
        asked = []

        class FakeBackend:
            def generate(self, system, user, max_new_tokens):
                item_id = next(i for i in replies if ("Item id: %s\n" % i) in user)
                asked.append(item_id)
                if replies[item_id].get("raise"):
                    raise RuntimeError("fixture failure")
                return {"text": replies[item_id]["reply"], "payload": system + "\n" + user,
                        "form": "fixture_messages"}

        loaded_before = {m for m in MODEL_LIBRARIES if m in sys.modules}
        with tempfile.TemporaryDirectory(prefix="b1_check_") as tmp:
            out = Path(tmp) / "out"
            summary = self.tool.run(BUNDLE, ITEMS, out, backend=FakeBackend(), reader=self._reader(),
                                    run_id="b1-fixture")
            self.assertEqual(sorted(asked), sorted(replies), "items asked")
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
            self.assertIn("CONV-QA-01: The line total must equal", sent)
            rates = {k: v["parse_rate"] for k, v in summary["benchmarks"].items()}
            self.assertEqual(sorted(rates.values()), [0.0, 0.0, 1.0, 1.0])
        self.assertEqual({m for m in MODEL_LIBRARIES if m in sys.modules} - loaded_before, set(),
                         "B1 loaded a model library with a mocked backend")

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

    def test_prompt_is_the_preregistered_text(self):
        if not PREREGISTRATION.is_file():
            self.skipTest("docs/benchmarks/PREREGISTRATION.md is not present here")
        prereg = PREREGISTRATION.read_text(encoding="utf-8")
        start = prereg.index("### 5.4")
        section = prereg[start:prereg.index("\n### ", start + 1)]
        self.assertIn(self.spec["source"], ("docs/benchmarks/PREREGISTRATION.md section 5.4",))
        self.assertIn("```\n" + self.spec["system"] + "\n```", section)
        template = self.spec["user_template"]
        for slot, written in (("{document}", "{document, after the cut rule, as it stands in the bundle}"),
                              ("{conventions}", "{every convention in the bundle, as written in it, one per line with its rule id}"),
                              ("{item_id}", "{opaque item id}"), ("{rule_id}", "{the item's rule id}"),
                              ("{question}", "{the item's question line, below}"),
                              ("{label_lines}", "{the benchmark's label lines, below}"),
                              ("{undecided_label}", "{the benchmark's undecided label name}")):
            template = template.replace(slot, written)
        self.assertIn("```\n" + template + "\n```", section)
        for bench in self.spec["benchmarks"].values():
            self.assertIn("Question: `%s`" % bench["question"], section)
            self.assertIn("Labels: " + " / ".join("`%s`" % line for line in bench["labels"]), section)
            self.assertIn("Undecided label: `%s`." % bench["undecided"], section)

    def test_cut_rule(self):
        count = self.tool.words
        self.assertEqual(self.tool.cut_budget(1000, 100, 200), 668)
        paragraphs = [" ".join("w%d" % (8 * p + i) for i in range(8)) for p in range(3)]
        text = "\n\n".join(paragraphs)
        same, info = self.tool.cut_document(text, 24, count)
        self.assertEqual((same, info["cut"]), (text, False))
        note = self.tool.cut_note(16, 24)
        cut, info = self.tool.cut_document(text, 8 + count(note), count)
        self.assertEqual(cut, paragraphs[0] + "\n" + note)
        self.assertEqual((info["words_removed"], info["paragraphs_kept"]), (16, 1))
        note = self.tool.cut_note(21, 24)
        cut, info = self.tool.cut_document(text, 3 + count(note), count)
        self.assertEqual(cut, "w0 w1 w2\n" + note)
        self.assertEqual((info["words_removed"], info["paragraphs_kept"]), (21, 0))
        with self.assertRaises(ValueError):
            self.tool.cut_document(text, 2, count)
        items = [{"item_id": "x", "rule_id": "CONV-X", "benchmark": key}
                 for key in self.spec["benchmarks"]]
        overhead = self.tool.prompt_overhead(self.spec, items, [("CONV-X", "text")],
                                             lambda system, user: count(system) + count(user))
        longest = max(count(self.spec["system"]) + count(self.tool.render_user(
            self.spec, i["benchmark"], document="", conventions=[("CONV-X", "text")], item=i))
            for i in items)
        self.assertEqual(overhead, longest)

    def test_reader_from_configuration(self):
        import decoding_policy
        reader = self._reader()
        with mock.patch.dict(os.environ, {"SHIMMER_MODEL_MODE": "base"}):
            plain = self.tool.resolve_reader(ROOT)
        chosen = json.loads((ROOT / "config" / "local_models.json").read_text(encoding="utf-8"))
        self.assertEqual(reader["agent"], "PROCESSOR")
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
                    "mocked to fail and touches none, imports no model library, finds the planted "
                    "product mismatch, lists the unasked plan, and marks every file an ablation")


def check_bare_model():
    return _verdict([_run(BareModelChecks), _run(AbsentChecks)],
                    "B1 with a mocked backend writes exactly one reply record per item (a failed "
                    "call included) joined to one typed label by call id, asks no item of another "
                    "document, loads no model, parses the final-line JSON label or abstains, sends "
                    "the preregistered prompt, cuts by the section 5.3 rule, and reads its model "
                    "and decoding policy from the tracked configuration")


def check():
    results = [_run(PythonOnlyChecks), _run(BareModelChecks), _run(AbsentChecks)]
    return _verdict(results, "B2 makes no model call and marks its output an ablation; B1 writes "
                             "one reply record per item through reply_records.write, parses or "
                             "abstains, and reads its model from the tracked configuration")


if __name__ == "__main__":
    print(check())
