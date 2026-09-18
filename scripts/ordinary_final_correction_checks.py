"""Executed proofs of the four corrections after ordinary final run v5 (110990c1).

No weights, no torch, no provider. Every mechanism is exercised on fixtures and,
where the run's own evidence is on disk, on the v5 raw outputs themselves:

  A1  refs are grounded by Python's placement of indexed passages in source spans
      (bounded_extraction.grounding), not by an id written inside the span text;
  A2  the PROCESSOR call sends the two turns checkpoint 168 was evaluated on, and
      a DEV row rendered through the runtime builder reproduces the protocol's
      recorded prompt hash byte for byte;
  A3  a declared core-field alias (`confident` for `confidence`) is read as the
      canonical key when the canonical key is absent and the value maps without
      interpretation, and every application is recorded;
  A4  the typed-record worked example carries the agent's own required fields,
      and a document without an accepted PROCESSOR draft records VERIFIER as not
      called instead of asking it to verify nothing.

NEUTRALIZATIONS lists, per test, the one mechanism whose removal must make that
test fail (the integration gate runs neutralize/fail/restore/pass over them).
"""
import ast
import asyncio
import contextlib
import hashlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import agent_wrapper
import auditor_pairs
import bounded_extraction as extraction
import paired_review
import pairing_map
import compact_contracts as cc
from agent_wrapper import AgentWrapper, CallResult
from reference_builder import ReferenceIndex, paragraph_ranges, _PARA_RE

FIXTURE = json.loads((ROOT / "docs/fix/compact_contract_ab/fixture.json").read_text(encoding="utf-8"))
REAL = FIXTURE["real_document"]
V5 = ROOT / "docs/fix/ordinary_final_cloud_run_v5/downloaded/evidence/run"
V5_SHEET = ROOT / "benchmark/corpora/clinical_reference/context/result_sheet.md"
V5_SHEET_SHA256 = "d0f332c85d4a1ef419adfa7b18355f28ff129fffeefaeecc8bf2a4c9a4b368a2"
VALIDATED_KEYS = ["context_only_spans", "production_contract", "required_refs", "role",
                  "routed_rules", "source_spans", "supplied_refs"]
CHAT_TEMPLATE = "<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"


def contracts():
    return json.loads((ROOT / "config/agent_contracts.json").read_text(encoding="utf-8"))["contracts"]


def bare_wrapper(name, backend="local_producer"):
    w = object.__new__(AgentWrapper)
    w.name, w.backend, w.model, w.run_context, w.cost_tracker = name, backend, "fixture", None, None
    w.contract = contracts()[name]
    w.spec = {"does": ["fixture job"], "does_not": []}
    w.last_parse_trace = {}
    return w


def index_twice(text, doc):
    """The pipeline's own reference index over one document, context copy then
    operational copy, exactly as a review run indexes a document that is both."""
    index = ReferenceIndex(ROOT)
    for input_type in ("context", "operational"):
        index.index_document(input_type=input_type, document_id=doc, document_name=doc + ".md", text=text)
    return [e.as_dict() for e in index.find_by_document(doc)]


def compact_wire(spans, refs_for=None):
    return dict(items=[dict(span=extraction.wire_id(s), claims=[], questions=["Q for " + extraction.wire_id(s)],
                            uncertainty=[], status="extracted",
                            refs=list((refs_for or {}).get(extraction.wire_id(s), []))) for s in spans])


def raw_violation(agent, task):
    """The v5 raw output of one contract violation, or None when the evidence is absent."""
    folder = V5 / "audit/contract_violations"
    if not folder.exists():
        return None
    for path in sorted(folder.glob(agent + "_*" + task + ".txt")):
        return path.read_text(encoding="utf-8").split("# ---\n", 1)[1]
    return None


def v5_entries():
    path = V5 / "audit/reference_index.json"
    if not path.exists():
        return None
    return [e for e in json.loads(path.read_text(encoding="utf-8"))["entries"] if e.get("document_id") == "result_sheet"]


class Inputs(dict):
    def to(self, device):
        return self


class RecordingTokenizer:
    chat_template = "configured"

    def __init__(self):
        self.messages = []

    def apply_chat_template(self, messages, **kw):
        self.messages.append([dict(m) for m in messages])
        return CHAT_TEMPLATE.format(system=messages[0]["content"], user=messages[-1]["content"]) \
            if len(messages) == 2 else "USER-ONLY:" + messages[-1]["content"]

    def __call__(self, prompt, **kw):
        return Inputs(input_ids=SimpleNamespace(shape=(1, 3)))

    def decode(self, ids, **kw):
        return '{"items":[]}'


class Output:
    def __init__(self, ids):
        self.ids, self.shape = list(ids), (1, len(ids))

    def __getitem__(self, key):
        return self.ids


TORCH = SimpleNamespace(no_grad=contextlib.nullcontext, cuda=SimpleNamespace(is_available=lambda: False))


def wide_build_prompt(self, pkg, work):
    """build_prompt as it was before the correction: the wide agent prompt, whatever
    the wrapper carries in _compact_messages."""
    work_str = work if isinstance(work, str) else json.dumps(work, ensure_ascii=False, indent=2)
    stable = self._stable_agent_block() + "\n\n" + self._execution_instructions()
    st = pkg.stable_text()
    if st:
        stable = stable + "\n## Context\n" + st
    dyn = "\n\n".join(f"=== {h} ===\n{b}" for h, b in pkg.dynamic_sections() if h != "WORK_PAYLOAD")
    return stable, (dyn + "\n\n" if dyn else "") + f"## Work payload\n{work_str}\n"


def concatenating_dispatch(self, stable_prefix, dynamic_suffix="", **kwargs):
    """dispatch as it was before the correction: one concatenated user turn."""
    full = stable_prefix + ("\n\n" + dynamic_suffix if dynamic_suffix else "")
    return self.call_local(full, **kwargs)


# Captured before any patch so a neutralised stand-in cannot call itself.
_ORIGINAL_AMENDMENT_FROM_FINDING = paired_review.amendment_from_finding


def no_grounding(text, spans, entries):
    aliases = [extraction.wire_id(s) for s in spans]
    return {a: [] for a in aliases}, {a: [] for a in aliases}, []


class CorrectionChecks(unittest.TestCase):
    # ---- A1: grounding by Python's passage placement ------------------------------

    def test_grounding_places_each_indexed_passage_in_its_span(self):
        text, doc = REAL["source"], REAL["doc"]
        self.assertNotRegex(text, r"REF-\d{4}|CLM-")
        entries = index_twice(text, doc)
        spans = extraction.ledger(text, doc)
        self.assertGreater(len(spans), 1)
        citable, markers, supplied = extraction.grounding(text, spans, entries)
        placed = [ref for group in citable.values() for ref in group]
        self.assertEqual(sorted(placed), sorted(e["ref_id"] for e in entries))  # every entry, once
        self.assertEqual(len(placed), len(set(placed)))
        operational = {e["ref_id"] for e in entries if e["input_type"] == "operational"}
        self.assertTrue(supplied and set(supplied) <= operational)  # the shown id is the operational copy's
        ranges = paragraph_ranges(text)
        self.assertEqual([p for _, _, p in ranges], [p.strip() for p in _PARA_RE.split(text) if p.strip()])
        for span in spans:
            alias = extraction.wire_id(span)
            shown = extraction.annotate(span.text, markers[alias])
            for offset, ref in markers[alias]:
                self.assertIn("(" + ref + ")", shown)
                self.assertTrue(any(min(end, span.end) - span.start == offset for _, end, _ in ranges))
            self.assertEqual(shown.replace(" (REF-", "").count(")"), span.text.count(")") + len(markers[alias]))
        # An entry whose paragraph index does not fit the text is skipped, never guessed.
        foreign = dict(entries[0], ref_id="REF-7777", location=dict(entries[0]["location"], paragraph=999))
        self.assertNotIn("REF-7777", [r for g in extraction.grounding(text, spans, entries + [foreign])[0].values() for r in g])

    def test_grounding_correct_citation_passes_fabricated_and_mismatched_fail(self):
        text, doc = REAL["source"], REAL["doc"]
        entries = index_twice(text, doc)
        spans = extraction.ledger(text, doc)
        citable, _, _ = extraction.grounding(text, spans, entries)
        first, second = extraction.wire_id(spans[0]), extraction.wire_id(spans[1])
        own = citable[first][0]
        result = cc.producer(compact_wire(spans, {first: [own]}), spans, doc, citable)
        self.assertEqual(result["items"][0]["ref_ids"], [own])
        self.assertEqual("".join(i["draft_text"] for i in result["items"]), text)
        with self.assertRaisesRegex(ValueError, "Ungrounded extraction evidence"):
            cc.producer(compact_wire(spans, {first: ["REF-9999"]}), spans, doc, citable)  # invented
        with self.assertRaisesRegex(ValueError, "Ungrounded extraction evidence"):
            cc.producer(compact_wire(spans, {first: [citable[second][0]]}), spans, doc, citable)  # another span's passage
        with self.assertRaisesRegex(ValueError, "Ungrounded extraction evidence"):
            cc.producer(compact_wire(spans, {first: [own]}), spans, doc, None)  # no placement, no inline id: refused as before
        inline = FIXTURE["source"]
        inline_spans = extraction.ledger(inline, FIXTURE["doc"])
        wire = compact_wire(inline_spans, {extraction.wire_id(inline_spans[0]): ["REF-0001"]})
        self.assertEqual(cc.producer(wire, inline_spans, FIXTURE["doc"], None)["items"][0]["ref_ids"], ["REF-0001"])

    def test_grounding_v5_raw_outputs_correct_citation_passes_mismatched_refused(self):
        entries = v5_entries()
        raw = {task: raw_violation("PROCESSOR", task) for task in ("task-000003", "task-000004", "task-000007", "task-000008")}
        if entries is None or not V5_SHEET.exists() or any(v is None for v in raw.values()):
            self.skipTest("v5 evidence not on disk")
        text = V5_SHEET.read_text(encoding="utf-8")
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), V5_SHEET_SHA256)
        spans = extraction.ledger(text, "result_sheet")
        self.assertEqual([extraction.wire_id(s) for s in spans], ["s0", "s14c", "s1cd", "s251", "s2d3", "s35d", "s3e6"])
        citable, markers, supplied = extraction.grounding(text, spans, entries)
        self.assertEqual(len(supplied), 21)  # one shown id per indexed paragraph, the operational copy's
        self.assertTrue(all(ref.startswith("REF-00") and 37 <= int(ref[4:]) <= 57 for ref in supplied))
        by_task = {t: json.loads(v) for t, v in raw.items()}
        partitions = extraction.partitions(spans)

        def parse(task, owned):
            w = bare_wrapper("PROCESSOR")
            w._optimized_semantics = True
            cc.bind_producer(w, owned, "result_sheet", citable={extraction.wire_id(s): citable[extraction.wire_id(s)] for s in owned})
            return w.parse_contract_output(json.dumps(by_task[task]))
        parsed, missing = parse("task-000003", partitions[0])   # cited each span's own paragraph
        self.assertEqual(missing, [])
        self.assertEqual([i["ref_ids"] for i in parsed["items"]], [["REF-0039"], ["REF-0041"], ["REF-0045"], ["REF-0027"]])
        _, missing = parse("task-000008", partitions[1])         # cited the next paragraph's id each time
        self.assertEqual(missing, ["Ungrounded extraction evidence"])
        for task, owned in (("task-000004", partitions[1]), ("task-000007", partitions[0])):
            _, missing = parse(task, owned)                      # still refused: the uncertainty key is absent
            self.assertEqual(missing, ["Exact compact extraction fields required"])
        forged = json.loads(raw["task-000003"])
        forged["items"][0]["refs"] = ["REF-9999"]
        w = bare_wrapper("PROCESSOR")
        cc.bind_producer(w, partitions[0], "result_sheet", citable=citable)
        self.assertEqual(w.parse_contract_output(json.dumps(forged))[1], ["Ungrounded extraction evidence"])

    # ---- A2: the validated prompt shape --------------------------------------------

    def test_prompt_validated_messages_shape(self):
        text, doc = REAL["source"], REAL["doc"]
        entries = index_twice(text, doc)
        spans = extraction.ledger(text, doc)
        for owned in extraction.partitions(spans):
            system, user, citable, supplied = cc.validated_messages(text, owned, spans, entries)
            self.assertTrue(system.startswith(cc.PRODUCER))
            self.assertEqual(system, cc.validated_system())
            self.assertEqual(hashlib.sha256(system.encode("utf-8")).hexdigest(), cc.prompt_declaration()["system_sha256"])
            payload = json.loads(user)
            self.assertEqual(list(payload), VALIDATED_KEYS)
            self.assertEqual(user, cc.canonical(payload))
            self.assertEqual([s["alias"] for s in payload["source_spans"]], [extraction.wire_id(s) for s in owned])
            for shown, span in zip(payload["source_spans"], owned):
                self.assertNotEqual(shown["text"], span.text)  # marked
                self.assertEqual(re.sub(r" \(REF-\d{4}\)", "", shown["text"]), span.text)  # and nothing but marked
            self.assertEqual(payload["supplied_refs"], supplied)
            self.assertTrue(all(len(c["text"]) <= 400 + 12 * 4 for c in payload["context_only_spans"]))
            self.assertEqual(payload["required_refs"], [])
            self.assertEqual(payload["role"], "producer")
            self.assertEqual(payload["production_contract"], "semantic-task-v1")
            for needle in ("## Context", "## Work payload", "You are PROCESSOR", "CONV-", "LAW-"):
                self.assertNotIn(needle, system + user)
            self.assertLess(len(system) + len(user), 8000)
            self.assertEqual(list(citable), [extraction.wire_id(s) for s in owned])

    def test_prompt_dev_row_reproduces_the_protocol_hash(self):
        declaration = cc.prompt_declaration()
        protocol = json.loads((ROOT / declaration["validated_protocol"]).read_bytes().replace(b"\r\n", b"\n").decode("utf-8"))
        rows = {r["example_id"]: r for r in json.loads((ROOT / declaration["validated_dataset"]).read_text(encoding="utf-8"))}
        prepared = {r["example_id"]: r for r in json.loads((ROOT / declaration["validated_prepared_dev"]).read_text(encoding="utf-8"))}
        checked = 0
        for example_id in protocol["dev_ids"][:12]:
            row = rows[example_id]["input"]
            payload = cc.validated_payload([(s["alias"], s["text"]) for s in row["source_spans"]],
                                           [(s["alias"], s["text"]) for s in row["context_only_spans"]],
                                           row["supplied_refs"], required_refs=row["required_refs"],
                                           routed_rules=row["routed_rules"])
            self.assertEqual(payload["production_contract"], row["production_contract"])
            self.assertEqual(payload["role"], row["role"])
            rendered = CHAT_TEMPLATE.format(system=cc.validated_system(), user=cc.canonical(payload))
            self.assertEqual(rendered, prepared[example_id]["prompt"])
            self.assertEqual(hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
                             protocol["prompt_bindings"][example_id]["prompt_sha256"])
            checked += 1
        self.assertEqual(checked, 12)
        # Through the model's own template when it is on disk (never fetched).
        try:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from transformers import AutoTokenizer
            tok = AutoTokenizer.from_pretrained("unsloth/Qwen2.5-7B-Instruct-bnb-4bit", local_files_only=True)
        except Exception:
            return
        example_id = protocol["dev_ids"][0]
        row = rows[example_id]["input"]
        payload = cc.validated_payload([(s["alias"], s["text"]) for s in row["source_spans"]],
                                       [(s["alias"], s["text"]) for s in row["context_only_spans"]],
                                       row["supplied_refs"], required_refs=row["required_refs"], routed_rules=row["routed_rules"])
        rendered = tok.apply_chat_template([{"role": "system", "content": cc.validated_system()},
                                            {"role": "user", "content": cc.canonical(payload)}],
                                           tokenize=False, add_generation_prompt=True)
        self.assertEqual(hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
                         protocol["prompt_bindings"][example_id]["prompt_sha256"])

    def test_prompt_build_returns_the_two_turns_and_no_context(self):
        w = bare_wrapper("PROCESSOR")
        w._stable_agent_block = lambda: "STABLE"
        w._execution_instructions = lambda: "EXEC"
        pkg = SimpleNamespace(stable_text=lambda: "CTX", dynamic_sections=lambda: [("X", "y")], rendered=None)
        text, doc = REAL["source"], REAL["doc"]
        spans = extraction.ledger(text, doc)
        system, user, citable, supplied = cc.validated_messages(text, spans, spans, index_twice(text, doc))
        cc.bind_producer(w, spans, doc, citable=citable, messages=(system, user, supplied))
        self.assertEqual(w.build_prompt(pkg, {"unused": True}), (system, user))
        self.assertEqual(w._role_anchor_text(), "")
        self.assertEqual(w._compact_rendered["reference_ids"], supplied)
        plain = bare_wrapper("PROCESSOR")
        plain._stable_agent_block = lambda: "STABLE"
        plain._execution_instructions = lambda: "EXEC"
        stable, dynamic = plain.build_prompt(pkg, {"k": 1})
        self.assertIn("## Context", stable)
        self.assertIn("## Work payload", dynamic)

    def test_prompt_dispatch_sends_system_and_user_turns(self):
        w = bare_wrapper("PROCESSOR")
        w._optimized_semantics = True
        w._compact_messages = ("SYSTEM TURN", '{"items":[]}')
        calls, tok = [], RecordingTokenizer()
        model = SimpleNamespace(device="cpu", generation_config=SimpleNamespace(eos_token_id=[9]),
                                generate=lambda **kw: (calls.append(kw), Output([1, 2, 3, 9]))[1],
                                _shimmer_identity=dict(model_mode="base"))
        with patch.dict(os.environ, SHIMMER_MODEL_MODE="base"), \
                patch.object(agent_wrapper.importlib, "import_module", side_effect=lambda n: TORCH if n == "torch" else object()), \
                patch.object(agent_wrapper, "_load_qwen", return_value=(tok, model)):
            result = w.dispatch("SYSTEM TURN", '{"items":[]}', max_new_tokens=4)
        self.assertEqual(len(calls), 1)
        self.assertEqual(tok.messages, [[{"role": "system", "content": "SYSTEM TURN"}, {"role": "user", "content": '{"items":[]}'}]])
        self.assertEqual(result.usage["rendered_prompt_sha256"],
                         hashlib.sha256(CHAT_TEMPLATE.format(system="SYSTEM TURN", user='{"items":[]}').encode("utf-8")).hexdigest())
        self.assertTrue(result.usage["chat_template_applied"])
        raw = bare_wrapper("PROCESSOR")
        with patch.dict(os.environ, SHIMMER_MODEL_MODE="base"), \
                patch.object(agent_wrapper.importlib, "import_module", side_effect=lambda n: TORCH if n == "torch" else object()), \
                patch.object(agent_wrapper, "_load_qwen", return_value=(tok, model)):
            with self.assertRaisesRegex(ValueError, "system message"):
                raw.call_local("x", max_new_tokens=4, system="s")  # never a system turn without the native template

    # ---- A3: the declared core-field alias ------------------------------------------

    def test_alias_declared_in_config_maps_only_unambiguous_values(self):
        declared = json.loads((ROOT / "config/agent_contracts.json").read_text(encoding="utf-8"))["core_field_aliases"]
        self.assertEqual(declared, {"confident": "confidence"})
        self.assertEqual(agent_wrapper.core_field_aliases(), declared)
        cases = [({"confident": "CONFIDENT"}, "CONFIDENT", True), ({"confident": "uncertain"}, "UNCERTAIN", True),
                 ({"confident": True}, "CONFIDENT", True), ({"confident": False}, "UNCERTAIN", True),
                 ({"confident": "maybe"}, None, False), ({"confident": 0.9}, None, False),
                 ({"confidence": "UNCERTAIN", "confident": "CONFIDENT"}, "UNCERTAIN", False),
                 ({"confidance": "CONFIDENT"}, None, False)]
        for item, expected, applied in cases:
            obj = {"agent": "ARCHIVIST", "doc_id": "d", "items": [dict(item, ref="REF-0001", kind="finding")]}
            notes = agent_wrapper.normalize_core_aliases(obj)
            self.assertEqual(notes, ["items[0].confident->confidence"] if applied else [], item)
            self.assertEqual(obj["items"][0].get("confidence"), expected, item)
            w = bare_wrapper("ARCHIVIST")
            missing = w._contract_missing(obj)
            self.assertEqual("items[0].confidence" in missing, expected is None, item)

    def test_alias_v5_outputs_parse_and_the_mapping_is_recorded(self):
        raws = {("ARCHIVIST", "task-000000"): raw_violation("ARCHIVIST", "task-000000"),
                ("LEGAL_ANALYST", "task-000009"): raw_violation("LEGAL_ANALYST", "task-000009"),
                ("EDITOR_CLERK", "task-000017"): raw_violation("EDITOR_CLERK", "task-000017")}
        synthetic = json.dumps({"agent": "ARCHIVIST", "doc_id": "d", "items": [
            {"confident": "CONFIDENT", "element": "fixture", "ref": "REF-0001", "ref_ids": ["REF-0001"], "kind": "inventory"}]})
        for (agent, task), raw in list(raws.items()) + [(("ARCHIVIST", "synthetic"), synthetic)]:
            if raw is None:
                continue
            self.assertIn('"confident"', raw)
            w = bare_wrapper(agent)
            parsed, missing = w.parse_contract_output(raw)
            self.assertEqual(missing, [], (agent, task))
            self.assertEqual(w.last_contract_normalizations, ["items[0].confident->confidence"], (agent, task))
            item = parsed["items"][0]
            self.assertIn(item["confidence"], ("CONFIDENT", "UNCERTAIN"))
            self.assertNotIn("confident", item)
        if all(v is None for v in raws.values()):
            self.skipTest("v5 evidence not on disk; synthetic case only")

    def test_alias_application_travels_with_result_bus_and_observation(self):
        from constitution import Constitution
        from message_bus import MessageBus
        from run_context import for_run_dir
        with tempfile.TemporaryDirectory() as folder:
            ctx = for_run_dir(ROOT, Path(folder))
            bus = MessageBus.open(Path(folder) / "bus.jsonl")
            w = AgentWrapper("EDITOR_CLERK", Constitution.load(ROOT / "config/constitution.json"), bus,
                             {"EDITOR_CLERK": dict(backend="local_producer", model="fixture")}, contracts(),
                             keys={"fixture": True}, run_context=ctx)
            raw = json.dumps({"agent": "EDITOR_CLERK", "doc_id": "d", "items": [
                {"confident": True, "kind": "editorial_observation", "rationale": "Fixture.", "ref": "REF-0001",
                 "ref_ids": ["REF-0001"], "verdict": "sound"}]})
            w.dispatch = lambda *a, **k: CallResult("local_producer", "fixture", raw, usage={"truncated": False})
            result = w.run_task(work_payload={"task": "fixture", "document_id": "d"})
            self.assertTrue(result["ok"])
            self.assertEqual(result["contract_normalized"], ["items[0].confident->confidence"])
            self.assertEqual(result["parsed"]["items"][0]["confidence"], "CONFIDENT")
            posted = [m for m in bus.read_all() if m["body"].get("event") == "AGENT_OUTPUT"][-1]
            self.assertEqual(posted["body"]["contract_normalized"], ["items[0].confident->confidence"])
            rows = [json.loads(l) for l in (ctx.logs_dir() / "generation_observation.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(rows[-1]["contract_normalized"], ["items[0].confident->confidence"])
            self.assertIs(rows[-1]["contract_valid"], True)

    # ---- A4: the typed-record example and the no-draft VERIFIER call ------------------

    def test_verifier_record_example_carries_required_fields(self):
        for agent in ("VERIFIER", "LEGAL_ANALYST"):
            w = bare_wrapper(agent, backend="local_auditor")
            text = w._finding_record_text()
            self.assertTrue(text)
            example = json.loads(text.split("Worked example: ", 1)[1].split("\n", 1)[0])
            required = [f for f in w.contract["required"] if f not in ("ref", "kind", "confidence")]
            for field in required:
                self.assertIn(field, example, (agent, field))
            self.assertIn("relation", example)
            self.assertIn("record_verdict", example)
            self.assertIn(str(required), text)
            self.assertIn("never replaces them", text)
        self.assertEqual(bare_wrapper("ARCHIVIST")._finding_record_text(), "")  # no record section for the rest

    def test_verifier_v5_raw_output_still_fails_the_contract(self):
        raw = raw_violation("VERIFIER", "task-000010")
        if raw is None:
            self.skipTest("v5 evidence not on disk")
        w = bare_wrapper("VERIFIER", backend="local_auditor")
        parsed, missing = w.parse_contract_output(raw)
        self.assertEqual(sorted(missing), sorted(["items[0].paragraph", "items[0].finding", "items[0].severity", "items[0].reasoning"]))

    def _phase_5(self, state):
        """state: 'complete' (accepted delivery), 'failed' (no accepted items),
        'partial' (a partition-merged delivery with one partition missing)."""
        import pipeline
        import agent_activation as activation
        from harness.run_agent import build_orchestrator
        calls = []

        async def fake_run_one(wrapper, work_payload, run_objectives, **kwargs):
            calls.append((wrapper.name, dict(work_payload)))
            return {"ok": True, "agent": wrapper.name, "parsed": {"agent": wrapper.name, "doc_id": "probe", "items": []},
                    "call_id": "call-" + wrapper.name, "contract_missing": [], "error": None, "truncated": False}
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"SHIMMER_BACKEND_PROFILE": "local"}):
            orch = build_orchestrator(ROOT, Path(folder))
            for name, (backend, model) in pipeline._LOCAL_PROFILE.items():
                orch.registry[name].update(backend=backend, model=model)
            audit = activation.initialize(orch.run_context, orch.registry, "sparse")
            doc = {"id": "probe", "name": "probe.md", "text": "## Entry A\nA declared source passage.\n"}
            draft = {"agent": "PROCESSOR", "doc_id": "probe", "items": [
                {"section_id": "s", "draft_text": doc["text"], "extraction_method": "source_span", "ref": "document-level",
                 "kind": "extraction", "confidence": "UNCERTAIN", "item_id": "PROCESSOR:probe:s", "revision": 1}]}
            if state == "partial":
                production = [{"scope": "doc", "doc_id": "probe", "agent": "PROCESSOR", "ok": False, "complete": False,
                               "parsed": draft, "partition_calls": ["c0", "c1"], "missing_partitions": [1],
                               "source_ownership": [], "error": "incomplete_extraction", "truncated": False}]
            else:
                processor_ok = state == "complete"
                production = [{"scope": "doc", "doc_id": "probe", "agent": "PROCESSOR", "ok": processor_ok,
                               "parsed": draft if processor_ok else None, "call_id": "proc-call",
                               "error": None if processor_ok else "incomplete_extraction", "truncated": False}]
            with patch.object(pipeline, "_run_one", fake_run_one):
                out = asyncio.run(pipeline.phase_5_audit(orch, {"offline_fixture": True}, [doc], production,
                                                         "Fixture objective", {"conventions": []}, ReferenceIndex(ROOT)))
            decisions = json.loads(audit.path.read_text(encoding="utf-8"))["decisions"]
            telemetry_path = orch.run_context.logs_dir() / "model_telemetry.jsonl"
            events = [json.loads(l) for l in telemetry_path.read_text(encoding="utf-8").splitlines() if l.strip()] if telemetry_path.exists() else []
        return calls, out, decisions, events

    def test_verifier_not_called_without_a_draft_and_recorded(self):
        calls, out, decisions, events = self._phase_5("failed")
        self.assertEqual([c[0] for c in calls], ["FACT_CHECKER"])
        self.assertEqual([r["agent"] for r in out], ["FACT_CHECKER"])
        self.assertFalse(calls[0][1]["processor_draft_available"])
        skipped = [d for d in decisions if d["agent"] == "VERIFIER" and not d["activated"]]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["reason"], "processor_draft_unavailable")
        self.assertEqual(skipped[0]["evidence"]["processor_error"], "incomplete_extraction")
        unavailable = [e for e in events if e["event"] == "auditor_pair_unavailable"]
        coverage = [e for e in events if e["event"] == "auditor_pair_coverage"]
        self.assertEqual([u["reason"] for u in unavailable], ["processor_draft_unavailable"])
        self.assertEqual(coverage[-1]["classifier_calls"], 0)
        self.assertEqual(coverage[-1]["unavailable_items"], 1)

    def test_verifier_called_with_a_draft(self):
        calls, out, decisions, _ = self._phase_5("complete")
        self.assertEqual([c[0] for c in calls], ["VERIFIER", "FACT_CHECKER"])
        self.assertEqual([r["agent"] for r in out], ["VERIFIER", "FACT_CHECKER"])
        self.assertTrue(calls[0][1]["processor_draft_available"])
        self.assertFalse(calls[0][1]["processor_draft_partial"])
        self.assertEqual([d for d in decisions if d["agent"] == "VERIFIER" and not d["activated"]], [])

    def test_verifier_called_with_a_partial_draft_and_marked(self):
        calls, out, decisions, _ = self._phase_5("partial")
        self.assertEqual([c[0] for c in calls], ["VERIFIER", "FACT_CHECKER"])
        payload = calls[0][1]
        self.assertTrue(payload["processor_draft_available"])
        self.assertTrue(payload["processor_draft_partial"])
        self.assertEqual(payload["processor_missing_partitions"], 1)
        self.assertIn("missing partitions", payload["processor_draft_note"])
        self.assertEqual(payload["processor_draft"]["items"][0]["item_id"], "PROCESSOR:probe:s")
        self.assertEqual([d for d in decisions if d["agent"] == "VERIFIER" and not d["activated"]], [])

    # ---- A9: the declared absence on CONV-L02 reaches the computed path ----------------

    def _clinical_review(self):
        """The clinical corpus through the real parser, splitter, pairing map and
        planner, with no model: (units_by_id, rules_by_id, entries, plans)."""
        import shutil
        import convention_parser
        import pairing_map
        corpus = ROOT / "benchmark/corpora/clinical_reference"
        if not (corpus / "conventions/lab_conventions.md").exists():
            self.skipTest("clinical corpus not on disk")
        with tempfile.TemporaryDirectory() as folder:
            tree = Path(folder)
            (tree / "input" / "conventions").mkdir(parents=True)
            shutil.copy(corpus / "conventions/lab_conventions.md", tree / "input/conventions/review_conventions.md")
            registry = convention_parser.parse_conventions(tree).as_dict()
        rules = registry["conventions"]
        rules_by_id = {r["id"]: r for r in rules}
        text = (corpus / "context/result_sheet.md").read_text(encoding="utf-8")
        units = pairing_map.split_units(text, document_id="result_sheet")
        units_by_id = {u["unit_id"]: u for u in units}
        vocabulary = pairing_map.field_vocabulary(units)
        entries = pairing_map.pair_units(units, rules, vocabulary=vocabulary)
        pairs = [(e["unit_id"], p["rule_id"]) for e in entries for p in e["paired"]]
        plans = paired_review.plan_calls(units_by_id, pairs, rules_by_id, vocabulary,
                                         needed_fields_for=lambda t: pairing_map.needed_fields(t, vocabulary))
        return units_by_id, rules_by_id, entries, plans

    def test_declared_absence_is_parsed_from_the_operator_heading(self):
        _, rules_by_id, _, _ = self._clinical_review()
        rule = rules_by_id["CONV-002"]
        self.assertEqual(rule["category"], "conv-l02")
        self.assertEqual(rule["severity"], "required")
        self.assertEqual([e["label"] for e in rule["scope"]], ["test"])
        self.assertEqual(rule["requires"], ["sample identifier", "measured value", "analysing laboratory"])
        # The other four rules are untouched by the declaration.
        for rid in ("CONV-001", "CONV-003", "CONV-004", "CONV-005"):
            self.assertEqual((rules_by_id[rid]["scope"], rules_by_id[rid]["requires"]), ([], []), rid)

    def test_declared_absence_reaches_the_computed_path_on_res_firth(self):
        """v5, v6 and v7 all missed RES-FIRTH's missing sample identifier because the
        pairing map rejected the completeness rule on the one unit that lacked the
        field. With the scope declared the rule pairs on every result and Python
        decides the absence with no call; the finding, the amendment and the
        scorer's reason check all name the missing identifier."""
        import pairing_map
        import sys
        units_by_id, rules_by_id, entries, plans = self._clinical_review()
        firth = next(e for e in entries if e["unit_id"] == "u06-result-res-firth")
        self.assertIn("CONV-002", [p["rule_id"] for p in firth["paired"]])
        self.assertEqual([r for r in firth["rejected"] if r["rule_id"] == "CONV-002"], [])
        absences = [p for p in plans if p["kind"] == "absence_computed"]
        self.assertEqual([(p["unit"]["unit_id"], p["rule"]["id"], p["checks"][0]["stated_field"]) for p in absences],
                         [("u06-result-res-firth", "CONV-002", "sample identifier")])
        # No unit is asked a model question about CONV-002 any more: Python decides it.
        self.assertEqual([p for p in plans if p["rule"].get("id") == "CONV-002" and p["kind"] != "absence_computed"], [])
        self.assertEqual([p for p in plans if p["kind"] == "absence_judged"], [])
        plan = absences[0]
        item = paired_review.finding_from_check(unit_id="u06-result-res-firth", rule=plan["rule"],
                                                check=plan["checks"][0], source_rule_id="CONV-L02", refs=["REF-0001"])
        self.assertEqual((item["relation"], item["record_verdict"], item["unit_id"]),
                         ("missing_field", "irregular", "u06-result-res-firth"))
        self.assertEqual(pairing_map._norm_label(item.get("field_label") or item.get("stated_field") or ""),
                         pairing_map._norm_label("sample identifier"))
        amendment = paired_review.amendment_from_finding(item, unit_texts=units_by_id)
        self.assertIsNotNone(amendment)
        self.assertIn("sample identifier", amendment["comment"].lower())
        self.assertIn("CONV-L02", amendment["comment"])
        self.assertEqual(amendment["derived_from"], "computed_finding")
        self.assertIn("## Result RES-FIRTH", amendment["original_text"])
        # The enriched key's claim for RES-FIRTH is confirmed by this finding.
        sys.path.insert(0, str(ROOT / "tools"))
        import score_corpus
        key = json.loads((ROOT / "benchmark/corpora/clinical_reference/answer_key.json").read_text(encoding="utf-8"))
        claim = next(e["claim"] for e in key["planted"] if e["unit"] == "RES-FIRTH")
        ok, why = score_corpus._reason_matches(claim, [item])
        self.assertTrue(ok, why)
        # CONV-001's pairing is undisturbed on every result (its bands are read from the
        # reference table by reference_bands_for, which this planner call does not wire;
        # three runs and the gate's own band checks hold that path).
        for entry in entries:
            self.assertIn("CONV-001", [p["rule_id"] for p in entry["paired"]], entry["unit_id"])
            self.assertIn("CONV-002", [p["rule_id"] for p in entry["paired"]], entry["unit_id"])

    # ---- A8: only computed findings become amendments ---------------------------------

    def _v7_phase6_inputs(self):
        """v7's own recorded phase-6 inputs: PRACTICE_AUDITOR's computed envelope and
        VERIFIER's model-authored one, each with the backend and model the run posted
        them under. Skips when the v7 evidence is not on disk."""
        path = ROOT / "docs/fix/ordinary_final_cloud_run_v7/downloaded/evidence/run/logs/agent_bus.jsonl"
        if not path.exists():
            return None, None
        computed = model = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            body = (json.loads(line).get("body") or {})
            payload = body.get("payload")
            if not isinstance(payload, dict) or not payload.get("items"):
                continue
            row = {"scope": "doc", "doc_id": "result_sheet", "agent": payload["agent"], "ok": True,
                   "backend": body.get("backend"), "model": body.get("model"),
                   "parsed": {"agent": payload["agent"], "doc_id": "result_sheet", "items": payload["items"]}}
            if payload["agent"] == "PRACTICE_AUDITOR":
                computed = row
            elif payload["agent"] == "VERIFIER":
                model = row
        return computed, model

    def test_promotion_only_computed_findings_reach_the_promoter(self):
        import paired_review
        computed, model = self._v7_phase6_inputs()
        if computed is None or model is None:
            self.skipTest("v7 evidence not on disk")
        # The run's own provenance: computed records are posted paired/python.
        self.assertEqual((computed["backend"], computed["model"]), ("paired", "python"))
        self.assertEqual(model["backend"], "local_auditor")
        selected = paired_review.computed_finding_items([computed, model], doc_id="result_sheet")
        self.assertEqual([i["unit_id"] for i in selected],
                         ["u01-result-res-alder", "u02-result-res-birch", "u05-result-res-elder"])
        # Every VERIFIER record is excluded, including the two that became v7's
        # false positive and its wrong-reason amendment.
        verifier_units = {i["unit_id"] for i in model["parsed"]["items"]}
        self.assertIn("u03-result-res-cedar", verifier_units)
        self.assertIn("u06-result-res-firth", verifier_units)
        self.assertFalse(verifier_units & {i["unit_id"] for i in selected} - {"u01-result-res-alder", "u02-result-res-birch", "u05-result-res-elder"})
        for item in model["parsed"]["items"]:
            self.assertFalse(any(item is s for s in selected))
        # Promotion over the narrowed input yields exactly the three computed amendments.
        built, added = paired_review.ensure_amendments_for_findings([], selected, unit_texts={})
        self.assertEqual((added, len(built)), (3, 3))
        self.assertEqual({a["finding_unit_id"] for a in built},
                         {"u01-result-res-alder", "u02-result-res-birch", "u05-result-res-elder"})
        # Against the pre-correction input, the two wrong ones come back.
        wide = [dict(i) for i in computed["parsed"]["items"] + model["parsed"]["items"]]
        wide_built, wide_added = paired_review.ensure_amendments_for_findings([], wide, unit_texts={})
        self.assertEqual(wide_added, 5)
        self.assertEqual({a["finding_unit_id"] for a in wide_built} - {a["finding_unit_id"] for a in built},
                         {"u03-result-res-cedar", "u06-result-res-firth"})

    def test_promotion_provenance_stamp_and_sentence_follow_the_source(self):
        import paired_review
        item = {"kind": "finding", "record_verdict": "irregular", "rule_id": "CONV-001",
                "unit_id": "u01", "relation": "above_band", "value_a": 148, "unit_a": "mmol/L",
                "value_b": 145, "unit_b": "mmol/L", "source_refs": ["REF-0001"],
                "field_label": "measured value", "explanation": "declared"}
        computed = paired_review.amendment_from_finding(item, unit_texts={})
        self.assertEqual(computed["derived_from"], "computed_finding")
        self.assertIn("Computed in code from the figures in this unit, not judged by a model.",
                      computed["comment"])
        authored = paired_review.amendment_from_finding(item, unit_texts={}, computed_provenance=False)
        self.assertEqual(authored["derived_from"], "model_finding")
        self.assertNotIn("Computed in code from the figures in this unit", authored["comment"])
        self.assertIn("Reported by the agent named above", authored["comment"])
        # Only the computed stamp is exempt from the arithmetic guard.
        _, refused_flagged = paired_review.suppress_contradicted_amendments(
            [authored], {}, {}, set())
        self.assertEqual(refused_flagged, [])  # no unit text: the guard abstains, it does not invent
        both, added = paired_review.ensure_amendments_for_findings(
            [], [item], unit_texts={}, computed_provenance=False)
        self.assertEqual((added, both[0]["derived_from"]), (1, "model_finding"))

    def test_promotion_v7_deliverable_amendments_are_reproduced_and_narrowed(self):
        """The two wrong v7 amendments exist in the shipped deliverable, carry the
        computed stamp, and the arithmetic guard does not catch them even when the
        stamp is corrected: the call-site narrowing is what removes them."""
        import paired_review
        path = ROOT / "docs/fix/ordinary_final_cloud_run_v7/downloaded/evidence/run/deliverables/result_sheet/review_data.json"
        if not path.exists():
            self.skipTest("v7 evidence not on disk")
        shipped = json.loads(path.read_text(encoding="utf-8"))["amendments"]
        wrong = [a for a in shipped if a["finding_unit_id"] in ("u03-result-res-cedar", "u06-result-res-firth")]
        self.assertEqual(len(wrong), 2)
        for a in wrong:
            self.assertEqual(a["derived_from"], "computed_finding")
            self.assertIn("Computed in code from the figures in this unit, not judged by a model.", a["comment"])
        text = (ROOT / "benchmark/corpora/clinical_reference/context/result_sheet.md")
        if not text.exists():
            self.skipTest("corpus not on disk")
        import pairing_map
        unit_texts = paired_review.unit_texts_for(text.read_text(encoding="utf-8"), "result_sheet")
        vocabulary = set()
        for unit in unit_texts.values():
            vocabulary |= pairing_map.unit_fields(unit.get("text", ""))
        rules = {"CONV-001": {"id": "CONV-001", "rule": "The measured value stated for a result must fall "
                                                       "inside the reference range recorded for its test."}}
        corrected = [dict(a, derived_from="model_finding") for a in wrong]
        kept, refused = paired_review.suppress_contradicted_amendments(corrected, unit_texts, rules, vocabulary)
        # Measured, not assumed: the guard computes no check for a band rule on these
        # units, so it abstains on both. The stamp fix alone would not have removed them.
        self.assertEqual((len(kept), len(refused)), (2, 0))

    # ---- A5: the pairing gate on partial deliveries -----------------------------------

    def _merged_delivery(self, *, partial, receipt=True, truncated_partition=False):
        source = "## Entry A\nA declared source passage.\n\n## Entry B\nAnother passage.\n"
        spans = extraction.ledger(source, "probe")
        item = dict(item_id="PROCESSOR:probe:" + spans[0].id, revision=1, claims_referenced=[], open_questions=[],
                    uncertainty=[], extraction_status="empty", ref="REF-0001", ref_ids=["REF-0001"], kind="extraction",
                    confidence="UNCERTAIN", source_span_id=spans[0].id, provenance="source_span_reconstruction")
        receipts = [dict(producer_item_id=item["item_id"], producer_revision=1, producer_call_id="call-0",
                         item_hash=auditor_pairs.item_hash(item), source_span_ids=[spans[0].id])] if receipt else []
        producer = dict(ok=not partial, truncated=truncated_partition, complete=not partial, call_id=None,
                        parsed=dict(agent="PROCESSOR", doc_id="probe", items=[item]), source_ownership=receipts,
                        partition_calls=["call-0", "call-1"], missing_partitions=[1] if partial else [],
                        error="incomplete_extraction" if partial else None)
        refs = [dict(ref_id="REF-0001", document_id="probe", input_type="operational", location={},
                     text_excerpt="A declared source passage.")]
        return dict(id="probe", text=source), producer, refs

    def test_pairing_partial_delivery_pairs_receipt_bound_items_and_marks_them(self):
        doc, partial, refs = self._merged_delivery(partial=True)
        pairs, unavailable, count = auditor_pairs.build("run", doc, partial, refs)
        self.assertEqual((len(pairs), unavailable, count), (1, [], 1))
        self.assertEqual(pairs[0]["record"]["delivery"], "partial")
        self.assertEqual(pairs[0]["record"]["ownership"], "compact_partition")
        auditor_pairs.validate(pairs[0]["record"])
        doc, complete, refs = self._merged_delivery(partial=False)
        self.assertEqual(auditor_pairs.build("run", doc, complete, refs)[0][0]["record"]["delivery"], "complete")
        # A merged delivery whose other partition was truncated still pairs the items it kept.
        doc, kept, refs = self._merged_delivery(partial=True, truncated_partition=True)
        self.assertEqual(len(auditor_pairs.build("run", doc, kept, refs)[0]), 1)
        # Without a receipt a partial delivery's item is refused, even with an explicit ref.
        doc, unreceipted, refs = self._merged_delivery(partial=True, receipt=False)
        pairs, unavailable, _ = auditor_pairs.build("run", doc, unreceipted, refs)
        self.assertEqual((pairs, [u["reason"] for u in unavailable]), ([], ["partial_delivery_without_receipt"]))
        # A failed single delivery is refused exactly as before.
        doc, single, refs = self._merged_delivery(partial=False)
        del single["missing_partitions"]
        single.update(ok=False, complete=None)
        pairs, unavailable, _ = auditor_pairs.build("run", doc, single, refs)
        self.assertEqual((pairs, [u["reason"] for u in unavailable]), ([], ["incomplete_producer_delivery"]))
        self.assertTrue(auditor_pairs.contract_self_check())

    def test_pairing_coverage_reports_pairs_from_a_partial_delivery(self):
        import model_telemetry
        doc, partial, refs = self._merged_delivery(partial=True)
        w = SimpleNamespace(name="VERIFIER", backend="local_auditor", run_context=None, _parent_call_ids=[],
                            _auditor_pair_request=dict(document=doc, producer=partial, references=refs))
        events = []
        with patch.dict(os.environ, SHIMMER_MODEL_MODE="final"), \
                patch.object(auditor_pairs, "predict", return_value=("OMISSION", 10)), \
                patch.object(model_telemetry, "emit", side_effect=lambda c, event, **k: events.append(dict(event=event, **k))):
            payload = auditor_pairs.prepare_context(w, dict(task=auditor_pairs.TASK))
        coverage = [e for e in events if e["event"] == "auditor_pair_coverage"][-1]
        self.assertEqual((coverage["pairs_constructed"], coverage["classifier_calls"], coverage["delivery"],
                          coverage["pairs_from_partial_delivery"]), (1, 1, "partial", 1))
        pair = [e for e in events if e["event"] == "auditor_pair"][0]
        self.assertEqual((pair["delivery"], pair["auditor_relation"], pair["classifier_status"]),
                         ("partial", "OMISSION", "classified"))
        self.assertEqual(payload["auditor_pair_context"]["pairs"][0]["delivery"], "partial")
        # The run-level summary carries the same figure, computed from real telemetry when it is on disk.
        telemetry = ROOT / "docs/fix/ordinary_final_cloud_run_v6/downloaded/evidence/run"
        if (telemetry / "logs/model_telemetry.jsonl").exists():
            rows = [json.loads(l) for l in (telemetry / "logs/model_telemetry.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
            scheduler = [json.loads(l) for l in (telemetry / "audit/execution_topology.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
            summary = model_telemetry.summarize(rows, scheduler)
            self.assertEqual(summary["auditor_pairing"]["pairs_from_partial_delivery"], 0)
            self.assertEqual(summary["auditor_pairing"]["partial_deliveries"], 0)

    # ---- A6: bounded requests carry the validated layout -------------------------------

    def test_layout_declared_request_size_within_validated_layout_and_used_live(self):
        import report_recommendations_checks as rr
        size = cc.request_size()
        declaration = cc.prompt_declaration()
        rows = json.loads((ROOT / declaration["validated_dataset"]).read_text(encoding="utf-8"))
        protocol = json.loads((ROOT / declaration["validated_protocol"]).read_bytes().replace(b"\r\n", b"\n").decode("utf-8"))
        dev = set(protocol["dev_ids"])
        validated = max(len(r["input"]["source_spans"]) for r in rows if r["example_id"] in dev)
        self.assertEqual(validated, max(len(r["input"]["source_spans"]) for r in rows))
        self.assertEqual(validated, 2)
        self.assertTrue(1 <= size <= validated, size)
        # The live partitioning uses the declared size: run the real _run_one with a
        # fake backend over a long source and count the owned aliases per request.
        rc = rr.RecommendationChecks("test_ledger_covers_preamble_tables_and_unicode")
        rc.setUp()
        try:
            tree = ast.parse((ROOT / "scripts/pipeline.py").read_text(encoding="utf-8"))
            fn = next(x for x in tree.body if isinstance(x, ast.AsyncFunctionDef) and x.name == "_run_one")
            namespace = dict(semantic_waves=rr.waves, asyncio=asyncio, time=rr.time,
                             _is_local_profile=lambda: False, _emit_progress=lambda **k: None)
            exec(compile(ast.Module(body=[fn], type_ignores=[]), "live_run_one", "exec"), namespace)
            pipeline_ns = SimpleNamespace(_run_one=namespace["_run_one"])
            runtime = rc.runtime(1)
            groups = []

            def dispatch(instance, stable, dynamic="", **kwargs):
                payload = json.loads(dynamic)
                ids = [s["alias"] for s in payload["source_spans"]]
                groups.append(ids)
                items = [dict(span=x, claims=[], questions=[], uncertainty=[], status="empty", refs=[]) for x in ids]
                return rc.fake_result(instance, dict(items=items), False)
            state = rr.topology.ACTIVE.set(runtime)
            try:
                with patch.object(AgentWrapper, "dispatch", dispatch):
                    w = runtime.attach(rc.wrapper())
                    result = asyncio.run(rc._one(pipeline_ns, w, rr.SOURCE * 30))
            finally:
                rr.topology.ACTIVE.reset(state)
            spans = extraction.ledger(rr.SOURCE * 30, "fixture")
            self.assertTrue(result["ok"])
            self.assertEqual(len(groups), -(-len(spans) // size))
            self.assertTrue(all(len(g) <= size for g in groups))
            self.assertEqual(sum(len(g) for g in groups), len(spans))
        finally:
            rc.doCleanups()

    # ---- A7: the typed-record example from declared values ------------------------------

    def test_record_example_uses_declared_values_and_the_agents_own_verdict_field(self):
        cases = {"FACT_CHECKER": ("verdict", "CONFIRMED"), "LEGAL_ANALYST": ("verdict", "GROUNDED"),
                 "VERIFIER": ("finding", "MATCH")}
        for agent, (field, value) in cases.items():
            w = bare_wrapper(agent, backend="local_auditor")
            text = w._finding_record_text()
            example = json.loads(text.split("Worked example: ", 1)[1].split("\n", 1)[0])
            self.assertEqual(example[field], value, agent)
            self.assertIn(f"Keep your own `{field}` field as your contract defines it", text)
            self.assertNotIn("<your own contract's verdict value", text)
            for name in w.contract["required"]:
                if w._declared_values(name):
                    self.assertFalse(str(example[name]).startswith("<"), (agent, name))
        v = bare_wrapper("VERIFIER", backend="local_auditor")
        example = json.loads(v._finding_record_text().split("Worked example: ", 1)[1].split("\n", 1)[0])
        self.assertNotIn("verdict", example)  # VERIFIER's contract has no verdict field
        self.assertEqual((example["paragraph"], example["severity"]), (1, "low"))
        self.assertEqual(bare_wrapper("ARCHIVIST")._declared_values("title"), [])  # a type description is not an enumeration
        raw = raw_violation("FACT_CHECKER", "task-000009")
        if raw is not None:  # the v6 output is still refused: the validator maps nothing
            self.assertEqual(bare_wrapper("FACT_CHECKER", backend="local_auditor").parse_contract_output(raw)[1],
                             ["items[0].verdict"])


def _grouped(prefix):
    names = [n for n in unittest.defaultTestLoader.getTestCaseNames(CorrectionChecks) if n.startswith(prefix)]
    suite = unittest.TestSuite(CorrectionChecks(n) for n in names)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    return result, stream.getvalue()


def _verdict(prefixes, summary):
    ran, skipped, log = 0, 0, ""
    for prefix in prefixes:
        result, text = _grouped(prefix)
        ran += result.testsRun
        skipped += len(result.skipped)
        log += text
        if not result.wasSuccessful():
            return ("FAIL", text[-3000:])
    return ("PASS", "%d checks (%d skipped for absent v5 evidence): %s" % (ran, skipped, summary))


def check_grounding():
    return _verdict(("test_grounding_", "test_prompt_"),
                    "refs grounded by Python's passage placement, invented and mismatched refs refused, "
                    "the validated two-turn prompt reproduces the protocol's DEV prompt hash")


def check_alias():
    return _verdict(("test_alias_",), "declared alias read as the canonical key, recorded on result, bus and observation")


def check_verifier():
    return _verdict(("test_verifier_",), "typed-record example contract-complete, VERIFIER skipped and recorded without a draft, "
                                         "called with a partial draft marked and noted")


def check_pairing():
    return _verdict(("test_pairing_",), "a partition-merged delivery pairs its receipt-bound items, a single failed delivery "
                                        "is refused as before, partial pairs marked in the record, the coverage event and the summary")


def check_layout():
    return _verdict(("test_layout_",), "the declared request size is within the validated one-or-two-span layout and the live "
                                       "partitioning uses it")


def check_record():
    return _verdict(("test_record_",), "the typed-record example carries the agent's declared values and names its own verdict "
                                       "field; the v6 FACT_CHECKER output is still refused")


def check_declared_absence():
    return _verdict(("test_declared_absence_",), "CONV-L02's declared scope and required fields are parsed from the operator's "
                                                 "heading, RES-FIRTH's missing sample identifier reaches the computed absence "
                                                 "path with no model call, and the finding, the amendment and the key's reason "
                                                 "check all name the missing identifier")


def check_promotion():
    return _verdict(("test_promotion_",), "only findings Python computed reach the amendment promoter, the provenance stamp "
                                          "and sentence follow the source, and v7's two model-authored amendments are "
                                          "reproduced from the shipped deliverable and excluded by the narrowing")


# (test, owner, attribute, mutant): each neutralises the one mechanism the test asserts.
NEUTRALIZATIONS = [
    ("test_grounding_correct_citation_passes_fabricated_and_mismatched_fail", extraction, "grounding", no_grounding),
    ("test_grounding_v5_raw_outputs_correct_citation_passes_mismatched_refused", extraction, "grounding", no_grounding),
    ("test_prompt_validated_messages_shape", cc, "validated_system", lambda: cc.PRODUCER),
    ("test_prompt_dev_row_reproduces_the_protocol_hash", cc, "validated_system", lambda: cc.PRODUCER),
    ("test_prompt_build_returns_the_two_turns_and_no_context", AgentWrapper, "build_prompt", wide_build_prompt),
    ("test_prompt_dispatch_sends_system_and_user_turns", AgentWrapper, "dispatch", concatenating_dispatch),
    ("test_alias_v5_outputs_parse_and_the_mapping_is_recorded", agent_wrapper, "core_field_aliases", lambda: {}),
    ("test_alias_application_travels_with_result_bus_and_observation", agent_wrapper, "core_field_aliases", lambda: {}),
    ("test_verifier_record_example_carries_required_fields", AgentWrapper, "_record_example_required", lambda self, required: {}),
    ("test_verifier_not_called_without_a_draft_and_recorded", None, "_verifier_has_a_draft", lambda state: True),
    # Neutralise the selector by restoring the pre-correction behaviour: every
    # result's items, whoever authored them, which is what v7 passed to the promoter.
    # Neutralise the declaration's effect: a pairing map that reads no scope is the
    # pre-declaration behaviour, under which CONV-002 was rejected on RES-FIRTH.
    ("test_declared_absence_reaches_the_computed_path_on_res_firth", pairing_map, "scope_declaration",
     lambda rule: []),
    ("test_promotion_only_computed_findings_reach_the_promoter", paired_review, "computed_finding_items",
     lambda results, agent=None, doc_id=None: [i for r in results or []
                                               for i in ((r.get("parsed") or {}).get("items") or [])]),
    # Neutralise the provenance flag by ignoring it, which is the unconditional
    # "computed_finding" stamp and sentence v7 shipped.
    ("test_promotion_provenance_stamp_and_sentence_follow_the_source", paired_review, "amendment_from_finding",
     lambda item, **kw: _ORIGINAL_AMENDMENT_FROM_FINDING(item, **{**kw, "computed_provenance": True})),
    ("test_verifier_called_with_a_partial_draft_and_marked", None, "_accepted_draft",
     lambda proc: (((proc or {}).get("parsed") if proc and proc.get("ok") else None), False)),
    ("test_pairing_partial_delivery_pairs_receipt_bound_items_and_marks_them", auditor_pairs, "delivery_scope",
     lambda producer: ("single", False)),
    ("test_pairing_coverage_reports_pairs_from_a_partial_delivery", auditor_pairs, "delivery_scope",
     lambda producer: ("single", False)),
    ("test_layout_declared_request_size_within_validated_layout_and_used_live", cc, "request_size", lambda: 4),
    ("test_record_example_uses_declared_values_and_the_agents_own_verdict_field", AgentWrapper, "_declared_values",
     lambda self, field: []),
]


def _bind_pipeline_owner():
    """pipeline is imported lazily (it is heavy); the owner of the last neutralization is resolved here."""
    import pipeline
    return [(n, pipeline if o is None else o, a, m) for n, o, a, m in NEUTRALIZATIONS]


NEUTRALIZATIONS = _bind_pipeline_owner()


if __name__ == "__main__":
    unittest.main(verbosity=2)
