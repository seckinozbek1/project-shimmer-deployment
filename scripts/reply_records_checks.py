"""Gate check: every model reply is saved once, with its outcome (S1 Part 4).

No provider, no network, no weights. The two network SDKs are replaced by
recording stand-ins at the import the wrapper performs, the two local backends
by a stand-in tokenizer and model, and the Auditor896 classifier by a stand-in
returned from final_models.resident. Everything else runs live: run_task, the
four backend functions, auditor_pairs.prepare_context and predict, the draft
memo's own pipeline function, and the phase-6 not-promoted marking. Every run
folder is a temporary directory; with no run context nothing is written at all.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import agent_wrapper
import auditor_pairs
import bounded_extraction
import decoding_policy
import final_models
import finding_record
import reply_records
from constitution import Constitution
from message_bus import MessageBus
from run_context import RunContext

ROOT = Path(__file__).resolve().parents[1]
_REAL_IMPORT = importlib.import_module
_PLACEHOLDER = "TEST_CREDENTIAL_PLACEHOLDER"


class _Touched(BaseException):
    """Raised if a no-context call reaches the record writer (not an Exception,
    so the writer's own best-effort handler cannot swallow it)."""


# ---------- stand-ins ------------------------------------------------------------------

def fake_anthropic(replies, seen):
    class APITimeoutError(Exception):
        pass

    class Messages:
        def create(self, **kw):
            seen.append(kw)
            reply = replies.pop(0)
            if isinstance(reply, BaseException):
                raise reply
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=reply)], stop_reason="end_turn",
                                   usage=SimpleNamespace(input_tokens=5, output_tokens=7,
                                                         cache_creation_input_tokens=0, cache_read_input_tokens=0))

    class Anthropic:
        def __init__(self, **kw):
            self.messages = Messages()
    return SimpleNamespace(Anthropic=Anthropic, APITimeoutError=APITimeoutError)


def fake_openai(replies, seen):
    class APITimeoutError(Exception):
        pass

    class Completions:
        def create(self, **kw):
            seen.append(kw)
            reply = replies.pop(0)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply), finish_reason="stop")],
                                   usage=SimpleNamespace(prompt_tokens=5, completion_tokens=7, prompt_tokens_details=None))

    class OpenAI:
        def __init__(self, **kw):
            self.chat = SimpleNamespace(completions=Completions())
    return SimpleNamespace(OpenAI=OpenAI, APITimeoutError=APITimeoutError)


class Inputs(dict):
    def to(self, device):
        return self


class Output:
    def __init__(self, ids):
        self.ids, self.shape = list(ids), (1, len(ids))

    def __getitem__(self, key):
        return self.ids


class LocalModel:
    """A tokenizer and model in one: decode returns the next queued reply."""
    chat_template = "configured"

    def __init__(self, replies, seen):
        self.replies, self.seen = replies, seen
        self.device = "cpu"
        self.generation_config = SimpleNamespace(eos_token_id=[9])

    def apply_chat_template(self, messages, **kw):
        return "TEMPLATED:" + json.dumps(messages)

    def __call__(self, prompt, **kw):
        self.seen.append(prompt)
        return Inputs(input_ids=SimpleNamespace(shape=(1, 3)))

    def generate(self, **kw):
        return Output([1, 2, 3, 4, 9])

    def decode(self, ids, **kw):
        return self.replies.pop(0)


TORCH = SimpleNamespace(no_grad=contextlib.nullcontext, cuda=SimpleNamespace(is_available=lambda: False))
POLICY = dict(backend="fixture", status="fixture", source="fixture", sha256="", kwargs={"do_sample": False})


@contextlib.contextmanager
def backends(claude=(), gpt=(), local=(), seen=None):
    """Patch every model boundary; yield the lists of what each was sent."""
    seen = seen if seen is not None else {"claude": [], "gpt": [], "local": []}
    model = LocalModel(list(local), seen["local"])
    modules = {"anthropic": fake_anthropic(list(claude), seen["claude"]),
               "openai": fake_openai(list(gpt), seen["gpt"]), "torch": TORCH, "transformers": object()}
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(agent_wrapper.importlib, "import_module",
                                         side_effect=lambda n, *a: modules[n] if n in modules else _REAL_IMPORT(n, *a)))
        stack.enter_context(patch.object(agent_wrapper, "_load_qwen", return_value=(model, model)))
        stack.enter_context(patch.object(decoding_policy, "policy", return_value=dict(POLICY)))
        stack.enter_context(patch.dict(os.environ, SHIMMER_MODEL_MODE="base", SHIMMER_PROVIDER_TIMEOUT_S="5"))
        yield seen


def classifier_stand_in(label="MATCH", fail=False):
    def predict(ids, directory):
        if fail:
            raise RuntimeError("fixture numerical failure")
        return label
    classifier = SimpleNamespace(model=SimpleNamespace(config=SimpleNamespace(max_position_embeddings=10 ** 6)),
                                 predict=predict, _shimmer_identity=dict(model_mode="final", model_id="fixture-auditor-896"))
    tokenizer = SimpleNamespace(apply_chat_template=lambda messages, **k: [1, 2, 3])
    return tokenizer, classifier


def envelope(agent, items):
    return json.dumps({"agent": agent, "doc_id": "doc-1", "items": items})


def finding(token):
    relation = sorted(finding_record.relations())[0]
    return {"ref": "REF-0001", "kind": "finding", "confidence": "CONFIDENT", "relation": relation,
            "record_verdict": "irregular", "rule_id": "CONV-001", "unit_id": "u01", "explanation": token}


def note(token):
    return {"ref": "REF-0002", "kind": "observation", "confidence": "UNCERTAIN", "explanation": token}


def folder_files(path):
    return sorted(p for p in Path(path).rglob("*") if p.is_file()) if Path(path).exists() else []


# ---------- fixture run ----------------------------------------------------------------

class Fixture:
    BACKENDS = {"PRACTICE_AUDITOR": "claude_api", "STYLE_GUARDIAN": "openai_api",
                "LEGAL_ANALYST": "local_producer", "REDACTOR": "qwen_local",
                "FACT_CHECKER": "claude_api", "AMENDMENT_DRAFTER": "claude_api", "ARCHIVIST": "claude_api"}

    def __init__(self, root, sensitive=False):
        self.ctx = RunContext(project_root=Path(root), run_id="replyfixture", run_dir=Path(root) / "run")
        self.ctx.ensure()
        self.sensitive = sensitive
        self.bus = MessageBus.open(self.ctx.bus_path())
        self.con = Constitution.load(ROOT / "config" / "constitution.json")
        real = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
        self.registry = {name: dict(real[name], backend=backend, model="fixture-model-" + name.lower())
                         for name, backend in self.BACKENDS.items()}

    @property
    def replies(self):
        return reply_records.folder(self.ctx)

    def wrapper(self, name, run_context="same"):
        return agent_wrapper.AgentWrapper(
            name=name, constitution=self.con, bus=self.bus, registry=self.registry, contracts={},
            keys={"ANTHROPIC_API_KEY": _PLACEHOLDER, "OPENAI_API_KEY": _PLACEHOLDER},
            run_context=self.ctx if run_context == "same" else run_context, sensitive=self.sensitive)


def pair_request():
    doc = dict(id="doc-1", text="SECRET-PAYLOAD-AUDITOR source sentence.\n\nSecond source sentence.")
    spans = bounded_extraction.ledger(doc["text"], doc["id"], max_chars=1200)
    item = dict(item_id="PROCESSOR:doc-1:a", revision=1, claims_referenced=["CLM-1"], open_questions=[], uncertainty=[])
    producer = dict(ok=True, truncated=False, call_id="producer-call", parsed=dict(items=[item]),
                    source_ownership=[dict(producer_item_id=item["item_id"], producer_revision=1,
                                           item_hash=auditor_pairs.item_hash(item), producer_call_id="producer-call",
                                           source_span_ids=[spans[0].id])])
    return dict(document=doc, producer=producer, references=[])


def mocked_run(fx):
    """One run touching every outcome. Returns ({call_id: expected outcome}, secret tokens)."""
    import pipeline
    expected, results = {}, []
    seen = {"claude": [], "gpt": [], "local": []}
    payload = lambda token: {"task": "per_document_analysis", "document_id": "doc-1", "document_text": token}
    refusal = json.dumps({"agent": "ARCHIVIST", "doc_id": "doc-1", "items": [], "status": "refused"})
    with backends(claude=[envelope("PRACTICE_AUDITOR", [finding("SECRET-REPLY-A")]), refusal,
                          RuntimeError("fixture provider failure"), "SECRET-REPLY-MEMO"],
                  gpt=[envelope("STYLE_GUARDIAN", [note("SECRET-REPLY-B")])],
                  local=[envelope("LEGAL_ANALYST", [note("SECRET-REPLY-C")]), "SECRET-REPLY-D not json"],
                  seen=seen):
        r = fx.wrapper("PRACTICE_AUDITOR").run_task(work_payload=payload("SECRET-PAYLOAD-A"), phase="5.5", doc_id="doc-1")
        results.append(dict(r, doc_id="doc-1")); expected[r["call_id"]] = "not_promoted"
        r = fx.wrapper("ARCHIVIST").run_task(work_payload=payload("SECRET-PAYLOAD-R"))
        expected[r["call_id"]] = "refused"
        r = fx.wrapper("STYLE_GUARDIAN").run_task(work_payload=payload("SECRET-PAYLOAD-B"), items_are_advisory=True)
        expected[r["call_id"]] = "advisory_not_record"
        r = fx.wrapper("LEGAL_ANALYST").run_task(work_payload=payload("SECRET-PAYLOAD-C"))
        results.append(dict(r, doc_id="doc-1")); expected[r["call_id"]] = "accepted_to_bus"
        r = fx.wrapper("REDACTOR").run_task(work_payload=payload("SECRET-PAYLOAD-D"))
        expected[r["call_id"]] = "contract_violation"
        r = fx.wrapper("FACT_CHECKER").run_task(work_payload=payload("SECRET-PAYLOAD-E"))
        expected[r["call_id"]] = "backend_failure"
        # The draft memo, through the pipeline's own function (a direct call_claude).
        memo = pipeline._draft_generate_with_evidence(
            fx.wrapper("AMENDMENT_DRAFTER"), "Draft a memo.", "## Question\nSECRET-PAYLOAD-MEMO",
            passages=[], run_ctx=fx.ctx)
        assert memo == "SECRET-REPLY-MEMO", memo
    drafted = [r["call_id"] for r in reply_records.records(fx.replies) if r["agent"] == "AMENDMENT_DRAFTER"]
    expected.update({call_id: "free_text" for call_id in drafted})
    # Auditor896, through prepare_context and the real predict.
    verifier = SimpleNamespace(name="VERIFIER", backend="local_auditor", run_context=fx.ctx, sensitive=fx.sensitive,
                               _parent_call_ids=[], _auditor_pair_request=pair_request())
    with patch.dict(os.environ, SHIMMER_MODEL_MODE="final"), \
         patch.object(final_models, "resident", return_value=classifier_stand_in("MATCH")):
        auditor_pairs.prepare_context(verifier, dict(task=auditor_pairs.TASK))
    classifier_call = verifier._auditor_pair_state[0]["classifier_call_id"]
    expected[classifier_call] = "classified"
    # Phase 6: the model's irregular findings are withheld from promotion, exactly
    # as phase_6_synthesis selects them; their calls are then marked not_promoted.
    upstream = [dict(f, agent=r["agent"]) for r in results for f in agent_wrapper.decode_items(r["parsed"])]
    withheld = [f for f in upstream if finding_record.is_finding(f)
                and str(f.get("record_verdict") or "").lower() == "irregular"]
    reply_records.mark_not_promoted(fx.ctx, (results,), withheld, doc_id="doc-1")
    tokens = ["SECRET-REPLY-" + x for x in ("A", "B", "C", "D", "MEMO")] + \
             ["SECRET-PAYLOAD-" + x for x in ("A", "R", "B", "C", "D", "E", "MEMO", "AUDITOR")]
    return expected, tokens


class ReplyRecordChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="shimmer_replies_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def check_records(self, fx, expected):
        rows = reply_records.records(fx.replies)
        self.assertEqual(sorted(r["call_id"] for r in rows), sorted(expected), "one record per call, no more")
        self.assertEqual([r["sequence"] for r in rows], list(range(1, len(rows) + 1)))
        current = reply_records.outcomes(fx.replies)
        for row in rows:
            self.assertEqual(reply_records.outcome_of(fx.replies, row["call_id"]), expected[row["call_id"]], row["agent"])
            self.assertIn(row["call_id"], current, "every record has its outcome written")
            for part in ("payload", "reply"):
                if row[part] is not None:
                    self.assertEqual(set(row[part]) >= {"sha256", "length_bytes"}, True)
        by_agent = {r["agent"]: r for r in rows}
        self.assertEqual(by_agent["PRACTICE_AUDITOR"]["model_id"], "fixture-model-practice_auditor")
        self.assertEqual(by_agent["AUDITOR896"]["model_id"], "fixture-auditor-896")
        self.assertEqual(by_agent["AUDITOR896"]["model_mode"], "final")
        self.assertEqual(by_agent["LEGAL_ANALYST"]["model_mode"], "base")
        self.assertEqual(by_agent["LEGAL_ANALYST"]["decoding"]["decoding_kwargs"], POLICY["kwargs"])
        self.assertIsNone(by_agent["FACT_CHECKER"]["reply"])
        self.assertFalse(by_agent["FACT_CHECKER"]["backend_ok"])
        return rows

    def test_mocked_run_one_record_per_call_with_its_outcome(self):
        fx = Fixture(self.root)
        expected, tokens = mocked_run(fx)
        self.assertEqual(sorted(set(expected.values())),
                         sorted({"not_promoted", "advisory_not_record", "accepted_to_bus", "contract_violation",
                                 "refused", "backend_failure", "free_text", "classified"}))
        rows = self.check_records(fx, expected)
        text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
        for token in tokens:
            self.assertIn(token, text, "a non-sensitive run keeps reply and payload text: " + token)
        for row in rows:
            if row["payload"] is not None:
                data = row["payload"]["text"].encode("utf-8")
                self.assertEqual(row["payload"]["sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(row["payload"]["length_bytes"], len(data))
        self.assertEqual(len(folder_files(fx.ctx.contract_violations_dir())), 1,
                         "the contract-violation file is still written as before")

    def test_sensitive_run_keeps_hashes_and_lengths_only(self):
        fx = Fixture(self.root, sensitive=True)
        expected, tokens = mocked_run(fx)
        rows = self.check_records(fx, expected)
        for row in rows:
            self.assertTrue(row["sensitive"])
            for part in ("payload", "reply"):
                if row[part] is not None:
                    self.assertNotIn("text", row[part], row["agent"])
            self.assertNotIn("error", row)
        for path in folder_files(fx.replies):
            body = path.read_text(encoding="utf-8")
            for token in tokens:
                self.assertNotIn(token, body, "%s holds text in a sensitive run" % path.name)

    def run_backend(self, method, fx, name, *args, **kw):
        w = fx.wrapper(name)
        w._cost_call_id = "fixture-call-" + method
        try:
            with backends(claude=["reply-claude"], gpt=["reply-gpt"], local=["reply-local"]) as seen:
                result = getattr(w, method)(*args, **kw)
        finally:
            w._cost_call_id = ""
        self.assertTrue(result.ok, result.error)
        rows = reply_records.records(fx.replies)
        self.assertEqual(len(rows), 1, method + " writes exactly one record")
        self.assertEqual(rows[0]["call_id"], "fixture-call-" + method)
        self.assertEqual(rows[0]["agent"], name)
        self.assertEqual(rows[0]["model_id"], w.model)
        return rows[0], seen

    def test_call_claude_writes_one_record(self):
        fx = Fixture(self.root)
        row, seen = self.run_backend("call_claude", fx, "PRACTICE_AUDITOR", "stable", "dynamic")
        sent = agent_wrapper.AgentWrapper._messages_text(seen["claude"][0]["messages"])
        self.assertEqual(row["payload"]["sha256"], hashlib.sha256(sent.encode("utf-8")).hexdigest())
        self.assertEqual(row["reply"]["text"], "reply-claude")

    def test_call_gpt_writes_one_record(self):
        fx = Fixture(self.root)
        row, seen = self.run_backend("call_gpt", fx, "STYLE_GUARDIAN", "stable", "dynamic")
        sent = agent_wrapper.AgentWrapper._messages_text(seen["gpt"][0]["messages"])
        self.assertEqual(row["payload"]["sha256"], hashlib.sha256(sent.encode("utf-8")).hexdigest())
        self.assertEqual(row["reply"]["text"], "reply-gpt")

    def test_call_qwen_writes_one_record(self):
        fx = Fixture(self.root)
        row, seen = self.run_backend("call_qwen", fx, "REDACTOR", "probe prompt", max_new_tokens=4)
        self.assertEqual(row["payload"]["sha256"], hashlib.sha256(seen["local"][0].encode("utf-8")).hexdigest())
        self.assertEqual(row["reply"]["text"], "reply-local")

    def test_call_local_writes_one_record(self):
        fx = Fixture(self.root)
        row, seen = self.run_backend("call_local", fx, "LEGAL_ANALYST", "probe prompt", max_new_tokens=4)
        self.assertEqual(row["payload"]["sha256"], hashlib.sha256(seen["local"][0].encode("utf-8")).hexdigest())
        self.assertEqual(row["reply"]["text"], "reply-local")
        self.assertEqual(row["decoding"]["max_new_tokens"], 4)

    def test_auditor_predict_writes_one_record(self):
        fx = Fixture(self.root)
        pair = auditor_pairs.build("replyfixture", pair_request()["document"], pair_request()["producer"], [])[0][0]
        with patch.object(final_models, "resident", return_value=classifier_stand_in("OMISSION")):
            self.assertEqual(auditor_pairs.predict(pair, fx.ctx, call_id="fixture-classifier")[0], "OMISSION")
        rows = reply_records.records(fx.replies)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["agent"], rows[0]["call_id"], rows[0]["reply"]["text"]),
                         ("AUDITOR896", "fixture-classifier", "OMISSION"))
        self.assertIn("SECRET-PAYLOAD-AUDITOR", rows[0]["payload"]["text"])
        failed = auditor_pairs.build("replyfixture", pair_request()["document"], pair_request()["producer"], [])[0][0]
        with patch.object(final_models, "resident", return_value=classifier_stand_in(fail=True)):
            with self.assertRaises(RuntimeError):
                auditor_pairs.predict(failed, fx.ctx, call_id="fixture-failed")
        rows = reply_records.records(fx.replies)
        self.assertEqual(len(rows), 2, "a failed classification is still one record")
        self.assertFalse(rows[1]["backend_ok"])

    def test_no_run_context_writes_nothing_anywhere(self):
        fx = Fixture(self.root)
        output = ROOT / "output"
        before = sorted(str(p) for p in output.rglob("model_replies")) if output.exists() else []
        cwd_before = sorted(os.listdir(os.getcwd()))
        with patch.object(reply_records, "_sequence", side_effect=_Touched("writer reached")):
            with backends(claude=["a"], gpt=["b"], local=["c", "d"]):
                for method, name, args in (("call_claude", "PRACTICE_AUDITOR", ("s", "d")),
                                           ("call_gpt", "STYLE_GUARDIAN", ("s", "d")),
                                           ("call_qwen", "REDACTOR", ("p",)), ("call_local", "LEGAL_ANALYST", ("p",))):
                    self.assertTrue(getattr(fx.wrapper(name, run_context=None), method)(*args).ok)
            pair = auditor_pairs.build("x", pair_request()["document"], pair_request()["producer"], [])[0][0]
            with patch.object(final_models, "resident", return_value=classifier_stand_in()):
                auditor_pairs.predict(pair, None, call_id="x")
            self.assertIsNone(reply_records.write(None, agent="A", backend="b", model_id="m", reply="r"))
            self.assertFalse(reply_records.write_outcome(None, "x", "accepted_to_bus", source="fixture"))
            self.assertIsNone(reply_records.folder(SimpleNamespace(run_id="no-dir")))
        self.assertFalse(fx.replies.exists())
        after = sorted(str(p) for p in output.rglob("model_replies")) if output.exists() else []
        self.assertEqual(before, after)
        self.assertEqual(cwd_before, sorted(os.listdir(os.getcwd())))

    def test_outcomes_are_append_only_and_known(self):
        fx = Fixture(self.root)
        reply_records.write_outcome(fx.ctx, "c1", "accepted_to_bus", source="fixture")
        reply_records.write_outcome(fx.ctx, "c1", "not_promoted", source="fixture")
        lines = (fx.replies / reply_records.OUTCOMES_NAME).read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(x)["outcome"] for x in lines], ["accepted_to_bus", "not_promoted"])
        self.assertEqual(reply_records.outcome_of(fx.replies, "c1"), "not_promoted")
        self.assertEqual(reply_records.outcome_of(fx.replies, "never-written"), "not_decided")
        with self.assertRaises(ValueError):
            reply_records.write_outcome(fx.ctx, "c1", "promoted", source="fixture")

    def test_phase_6_marks_its_withheld_findings(self):
        """The executed marking above is reached from phase_6_synthesis with the
        same _withheld list it logs (wired, not a parallel copy)."""
        tree = ast.parse((ROOT / "scripts" / "pipeline.py").read_text(encoding="utf-8"))
        phase = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "phase_6_synthesis")
        calls = [ast.unparse(n) for n in ast.walk(phase) if isinstance(n, ast.Call)
                 and ast.unparse(n.func) == "reply_records.mark_not_promoted"]
        self.assertEqual(len(calls), 1)
        self.assertIn("_withheld", calls[0])


def check():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReplyRecordChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        first = (result.failures + result.errors)[0]
        return ("FAIL", f"{len(result.failures)} failures, {len(result.errors)} errors; first: "
                        f"{first[0].id().rsplit('.', 1)[-1]}: {first[1].strip().splitlines()[-1][:300]}")
    return ("PASS", f"{result.testsRun} cases: a mocked run saves exactly one record per model call "
                    f"(run_task, the draft memo, Auditor896) under <run>/audit/model_replies/ with its "
                    f"outcome (accepted_to_bus, advisory_not_record, not_promoted, contract_violation, "
                    f"refused, backend_failure, free_text, classified); a sensitive run keeps sha256 and length_bytes "
                    f"only; each backend function and auditor_pairs.predict writes one record; no run "
                    f"context writes nothing")


if __name__ == "__main__":
    unittest.main()
