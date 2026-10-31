"""E's evidence on B3's own prompts (docs/loop/DECISIONS.md D-061 item 4): replay the producer
prompts an earlier B3 run rendered, standalone, through the measurement paths, one model load.

An evaluation tool, not a review and not an arm. Two commands:

  extract (no model)
      py -3.12 benchmark/baselines/replay_prompts.py extract --records <run>/audit/model_replies
          [--records <another run's folder> ...] [--call-ids calls.json] [--dev | --agents A,B]
          --out replay_prompts.json [--min-chars N]
    Reads the reply records of one or more earlier runs (one JSON file per call, written by
    scripts/reply_records.py) and keeps every producer call (backend local_producer) whose
    rendered prompt text was saved (payload form rendered_prompt), or only the calls
    --call-ids lists (a JSON list of call ids, or of objects carrying `call_id`). It reads ONLY
    the payload, the call's identifiers (call id, agent, document id, the output allowance in
    its decoding record) and the reply's recorded SHA-256 (the reference a replay is compared
    with): never a reply's text, a label, an outcome or a key. A record of a sensitive run
    (hashes only) is refused, and so is any folder under benchmark/keys/. --dev adds the
    validated DEV rows of checkpoint 168 (the prepared prompts the compact extraction
    declaration names, each held to the protocol's prompt SHA-256, with the protocol's output
    cap) and, as their reference, the SHA-256 of each frozen DEV reply (DEV_REPLIES). It
    writes replay_prompts.json: per prompt its set (records or dev), source call id, agent,
    document id, the rendered prompt, its SHA-256, the output allowance and the reference
    reply's SHA-256, and the source runs. --agents VERIFIER,PRACTICE_AUDITOR keeps instead the
    calls of those envelope agents (config/envelope_decoding.json) on their declared backend,
    each with its backend and model id; a file holds one model's prompts. A --call-ids file whose
    objects each carry a `set` label counts each prompt under its own set.

  run (loads the tuned producer once, through the loader B1's tuned checkpoint uses)
      py -3.12 benchmark/baselines/replay_prompts.py run --prompts replay_prompts.json --out <dir>
          [--paths e,one_shot,sdpa,e_repeat] [--decision D-NNN] [--max-new-tokens N]
    Runs every prompt through each path, in order, on the same resident model:
      e         eager, chunked at 512 tokens (E, D-061; a measurement path)
      one_shot  eager, prefilled in one shot (a measurement path)
      sdpa      sdpa pinned to the memory-efficient backend, one shot: the run proper's
                setting under D-063
      e_repeat  E again, for determinism (a measurement path)
      sdpa_constrained  sdpa one shot under the compact producer's contract constraint
                (DECODING-B, scripts/contract_decoding.py), its declaration read back from the
                prompt's own canonical payload: the B3 producer's setting under DECODING-B
    e, one_shot and e_repeat are measurement paths and need --decision, the recorded decision
    that asks for them. Every call goes through the one shared generate helper
    (final_models.generate_with_prefill) under the frozen decoding policy, with the prompt's
    own output allowance (or --max-new-tokens). Per path it records the peak GPU memory
    (counters reset before the path, read after it) and per prompt the reply's SHA-256 and
    length, the output tokens and what the prefill measured (chunks, tail tokens, prefill
    seconds). An out-of-memory error or a refused kernel is recorded for that prompt and path
    (its kind, never retried) and the path goes on; a prompt over the context is refused before
    generating. Each call writes one reply record (hashes only) under <out>/audit/model_replies.
    It writes <out>/replay_measurement.json: the paths, the rows, and per pair of paths (e
    against one_shot, e against e_repeat, sdpa against one_shot, e against sdpa) the counts of
    byte-identical replies, of replies that parse to equal JSON, and of failures, over every
    prompt and over the prompts of at least three chunks. For a compact producer prompt every
    reply is also run through compact_contracts.producer, unchanged (`contract`: valid, or the
    validator's reason), a constrained reply carries what the constraint counted (steps,
    interventions, dead end), and a prompt with a reference reply is compared with it; the
    per-path totals by set are under `validity`, `reference` and `constraint`. Ids, hashes,
    counts, the validator's reasons and seconds only, never a prompt's or a reply's text.
    A file of envelope agents' prompts is replayed on their own model (the local auditor,
    loaded by the run's loader in a process set up as the run's) on sdpa and sdpa_constrained
    only; sdpa_constrained carries the envelope constraint of each prompt's own agent, and every
    reply is judged by the agent's envelope validator and run_task's completeness rule, unchanged.

The thresholds the E evidence is read against (D-060, D-061: at least 90 percent byte-identical
with one-shot eager and at least 95 percent label agreement on the tuned checkpoint) are applied
by whoever reads the counts; this tool decides nothing.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "scripts"
for _p in (str(SCRIPTS), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import final_models  # noqa: E402
import reply_records  # noqa: E402

SCHEMA = "b3-replay-prompts-v1"
MEASUREMENT_SCHEMA = "b3-replay-measurement-v1"
MEASUREMENT_FILE = "replay_measurement.json"
AGENT_LABEL = "E_EVIDENCE_REPLAY"
PHASE = "E_EVIDENCE"
PRODUCER_BACKEND = "local_producer"
# The paths, in the order run() takes them by default. A measurement path needs its decision.
# Under D-063 sdpa one shot is the run proper's setting; eager (one shot or chunked) is a
# measurement setting.
PATHS = {
    "e": {"attention": final_models.EAGER, "prefill_chunk": final_models.E_CHUNK_TOKENS, "measurement": True},
    "one_shot": {"attention": final_models.EAGER, "prefill_chunk": None, "measurement": True},
    "sdpa": {"attention": final_models.SDPA, "prefill_chunk": None, "measurement": False},
    "e_repeat": {"attention": final_models.EAGER, "prefill_chunk": final_models.E_CHUNK_TOKENS, "measurement": True},
    "sdpa_constrained": {"attention": final_models.SDPA, "prefill_chunk": None, "measurement": False,
                         "constraint": True},
}
DEFAULT_PATHS = ("e", "one_shot", "sdpa", "e_repeat")
PAIRS = (("e", "one_shot"), ("e", "e_repeat"), ("sdpa", "one_shot"), ("e", "sdpa"), ("sdpa_constrained", "sdpa"))
# --dev: the frozen DEV replies of checkpoint 168 (the evaluation run's own evidence), read for
# their SHA-256 only; the prompts and the protocol are the ones the compact extraction
# declaration names (config/compact_extraction_prompt.json).
DEV_REPLIES = "docs/fix/producer_tuning_v3_run/downloaded/evidence/checkpoint-168/full_dev.jsonl"
DEV_AGENT = "PROCESSOR_DEV"
# A prompt long enough to be fed in at least three chunks (D-061 item 4).
THREE_CHUNKS = 3
NEVER_READ = ("benchmark/keys",)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# extract (no model)


def _refuse_keys(folder):
    resolved = Path(folder).resolve()
    for part in NEVER_READ:
        if (ROOT / part).resolve() in (resolved, *resolved.parents):
            raise ValueError("a key folder is never read: " + part)


def _call_ids(path):
    """The call ids a --call-ids file lists: a JSON list of ids or of objects carrying `call_id`.
    When every object also carries `set` (lower case letters, digits, underscores; not `dev`),
    {call id: set}, and each prompt is counted under its own set."""
    if path is None:
        return None
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [v.get("call_id") if isinstance(v, dict) else v for v in value] if isinstance(value, list) else None
    if not ids or not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("--call-ids lists distinct call ids")
    if all(isinstance(v, dict) and "set" in v for v in value):
        import re
        if not all(isinstance(v["set"], str) and re.fullmatch(r"[a-z0-9_]+", v["set"]) and v["set"] != "dev" for v in value):
            raise ValueError("--call-ids names each set in lower case letters, digits and underscores, never dev")
        return {v["call_id"]: v["set"] for v in value}
    return set(ids)


def dev_prompts(root=ROOT):
    """The validated DEV rows of checkpoint 168 as replay prompts: the prepared prompt (held to
    the protocol's prompt SHA-256), the protocol's output cap, and the SHA-256 of the frozen
    reply as the reference. Nothing of a reply but its digest."""
    import compact_contracts
    declared = compact_contracts.prompt_declaration()
    protocol = json.loads((Path(root) / declared["validated_protocol"]).read_bytes().replace(b"\r\n", b"\n").decode("utf-8"))
    prepared = {r["example_id"]: r for r in json.loads((Path(root) / declared["validated_prepared_dev"]).read_text(encoding="utf-8"))}
    frozen = {}
    for line in (Path(root) / DEV_REPLIES).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            frozen[row["example_id"]] = _sha(row["raw_output"])
    cap = protocol["generation_kwargs"]["max_new_tokens"]
    rows = []
    for example_id in protocol["dev_ids"]:
        prompt = prepared[example_id]["prompt"]
        if _sha(prompt) != protocol["prompt_bindings"][example_id]["prompt_sha256"]:
            raise ValueError("a prepared DEV prompt differs from the protocol's: " + example_id)
        rows.append({"set": "dev", "source_call_id": example_id, "source_run_id": protocol["experiment"],
                     "agent": DEV_AGENT, "doc_id": example_id, "max_new_tokens": cap, "prompt_sha256": _sha(prompt),
                     "reference_reply_sha256": frozen[example_id], "prompt": prompt})
    return rows, {"dev_rows": len(rows), "protocol": declared["validated_protocol"], "replies": DEV_REPLIES}


def model_key(prompt):
    """The model a prompt is replayed on: the tuned producer for every producer prompt (a prompt
    with no backend is one), otherwise its backend and the model its call loaded."""
    backend = prompt.get("backend") or PRODUCER_BACKEND
    return (backend, None) if backend == PRODUCER_BACKEND else (backend, prompt.get("model_id"))


def envelope_agents(agents):
    """{agent: backend} for the named envelope agents (config/envelope_decoding.json); an agent
    the declaration does not name is refused."""
    import contract_decoding
    declared = contract_decoding.envelope_declaration()[0]["agents"]
    unknown = sorted(set(agents) - set(declared))
    if unknown:
        raise ValueError("--agents names an agent with no envelope declaration: " + ", ".join(unknown))
    return {agent: declared[agent]["backend"] for agent in agents}


def extract(folders, out, *, min_chars=0, call_ids=None, dev=False, agents=None):
    """replay_prompts.json from the reply records under `folders` (only the calls `call_ids`
    names, when given) and, with `dev`, the DEV rows (see the module text). With `agents`, the
    calls of those declared envelope agents on their own backend instead of the producer's
    (DECODING-B's envelope constraint); --dev is the producer's and is refused with it."""
    prompts, sources = [], []
    wanted = set(call_ids) if call_ids is not None else None
    if not folders and not dev:
        raise ValueError("name reply record folders, --dev, or both")
    chosen = envelope_agents(agents) if agents else None
    if chosen is not None and dev:
        raise ValueError("--dev adds producer prompts; a replay file holds one model's prompts")
    for folder in folders or ():
        _refuse_keys(folder)
        rows = reply_records.records(folder)
        if not rows:
            raise ValueError("no reply records under " + str(folder))
        kept = 0
        for row in rows:
            if chosen is None and row.get("backend") != PRODUCER_BACKEND:
                continue
            if chosen is not None and chosen.get(row.get("agent")) != row.get("backend"):
                continue
            if wanted is not None and row.get("call_id") not in wanted:
                continue
            payload = row.get("payload")
            if not isinstance(payload, dict) or payload.get("form") != "rendered_prompt":
                continue
            if row.get("sensitive") or not isinstance(payload.get("text"), str):
                raise ValueError("a sensitive run's records keep hashes only; its prompts cannot be replayed")
            text = payload["text"]
            if _sha(text) != payload.get("sha256"):
                raise ValueError("a saved prompt does not match its own SHA-256: call " + str(row.get("call_id")))
            if len(text) < int(min_chars):
                continue
            allowance = (row.get("decoding") or {}).get("max_new_tokens")
            reference = (row.get("reply") or {}).get("sha256")
            label = call_ids.get(row.get("call_id"), "records") if isinstance(call_ids, dict) else "records"
            prompts.append({"prompt_id": "p%04d" % (len(prompts) + 1), "set": label,
                            "source_call_id": row.get("call_id"),
                            "source_run_id": row.get("run_id"), "agent": row.get("agent"),
                            "backend": row.get("backend"), "model_id": row.get("model_id"),
                            "doc_id": row.get("doc_id"), "max_new_tokens": allowance if type(allowance) is int else None,
                            "prompt_sha256": payload["sha256"],
                            "reference_reply_sha256": reference if isinstance(reference, str) else None,
                            "prompt": text})
            if wanted is not None:
                wanted.discard(row.get("call_id"))
            kept += 1
        sources.append({"run_ids": sorted({str(r.get("run_id")) for r in rows}), "records": len(rows),
                        "producer_prompts": kept})
    if wanted:
        raise ValueError("%d listed call id(s) have no %s prompt in the records given"
                         % (len(wanted), "producer" if chosen is None else "named agent's"))
    if dev:
        rows, source = dev_prompts()
        for row in rows:
            prompts.append(dict({"prompt_id": "p%04d" % (len(prompts) + 1)}, **row))
        sources.append(source)
    if not prompts:
        raise ValueError("no %s prompt with its rendered text in the records given"
                         % ("producer" if chosen is None else "named agent's"))
    if len({model_key(p) for p in prompts}) > 1:
        raise ValueError("the records given hold prompts of more than one model; a replay file holds one model's prompts")
    value = {"schema": SCHEMA, "written_at": _now(), "sources": sources, "min_chars": int(min_chars),
             "prompt_count": len(prompts), "prompts": prompts}
    _write_json(out, value)
    return value


def load_prompts(path):
    """The prompts of a replay_prompts.json, each checked against its own SHA-256."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != SCHEMA or not isinstance(value.get("prompts"), list):
        raise ValueError("not a replay_prompts.json (" + SCHEMA + ")")
    if not value["prompts"] or value.get("prompt_count") != len(value["prompts"]):
        raise ValueError("replay_prompts.json holds no prompt, or its count is wrong")
    ids = set()
    for prompt in value["prompts"]:
        if not isinstance(prompt.get("prompt"), str) or _sha(prompt["prompt"]) != prompt.get("prompt_sha256"):
            raise ValueError("a prompt does not match its SHA-256: " + str(prompt.get("prompt_id")))
        if prompt.get("prompt_id") in ids:
            raise ValueError("prompt ids repeat")
        ids.add(prompt.get("prompt_id"))
    return value["prompts"]


# ---------------------------------------------------------------------------
# run


def path_record(name, decision=None):
    """The declared attention and prefill of one path (bare_model.attention_record, the rule
    B1's passes are held to): a measurement path only with its recorded decision."""
    import bare_model
    if name not in PATHS:
        raise ValueError("unknown path %r; paths are %s" % (name, ", ".join(PATHS)))
    spec = PATHS[name]
    if spec["measurement"] and decision is None:
        raise ValueError("path %s is a measurement path and needs --decision (the recorded decision)" % name)
    eager = spec["attention"] == final_models.EAGER
    chunk = spec["prefill_chunk"]
    return bare_model.attention_record(prefill_chunk=chunk, prefill_decision=decision if chunk else None,
                                       attention=spec["attention"], attention_decision=decision if eager else None)


class ReplayBackend:
    """The tuned producer, loaded once through bare_model's LocalBackend (the loader B1's tuned
    checkpoint uses: final_models.resident), called on an already rendered prompt."""

    def __init__(self, reader, run_context):
        import bare_model
        self.bare_model, self.reader = bare_model, reader
        self.local = bare_model.LocalBackend(reader, run_context)

    def prepare(self):
        return self.local.prepare()

    def count(self, prompt):
        tok, _ = self.local._loaded()
        return len(tok(prompt, add_special_tokens=False)["input_ids"])

    def max_context(self):
        return self.local.max_context()

    def generate(self, prompt, attention, max_new_tokens, constraint=False, agent=None):
        """One replayed call. With `constraint`, the compact producer's contract constraint
        (contract_decoding.for_prompt, its declaration read from the prompt's own payload), or
        with `agent` that envelope agent's constraint, rides beside the frozen decoding kwargs
        exactly as in a B3 call, and what it counted is returned. `truncated` is the run's own
        rule: the allowance spent without a stop token."""
        import torch
        import contract_decoding
        import decoding_policy
        tok, mdl = self.local._loaded()
        inputs = tok(prompt, return_tensors="pt", add_special_tokens=False).to(mdl.device)
        start = int(inputs["input_ids"].shape[1])
        constrained = (contract_decoding.for_prompt(prompt, tok, start, decoding_policy.effective_eos(self.reader["decoding"], mdl),
                                                    agent=agent)
                       if constraint else None)
        extra = constrained.generate_kwargs() if constrained is not None else {}
        with torch.no_grad(), self.bare_model.b1_attention(mdl, implementation=attention["attention_implementation"]) as observe:
            observed = observe()
            out, measured = final_models.generate_with_prefill(
                mdl, inputs, max_new_tokens=max_new_tokens, decoding_kwargs=self.reader["decoding"]["kwargs"],
                prefill=self.bare_model.prefill_of(attention), **extra)
        text = tok.decode(out[0][start:], skip_special_tokens=True)
        generated = int(out[0].shape[0]) - start
        import generation_observation
        _, truncated = generation_observation.local_stop(int(out[0][-1]) if generated else None,
                                                         decoding_policy.effective_eos(self.reader["decoding"], mdl),
                                                         generated, max_new_tokens)
        del inputs, out
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        result = {"text": text, "output_tokens": generated, "attention": dict(attention, **observed), "prefill": measured,
                  "truncated": truncated}
        if constrained is not None:
            result["decoding_constraint"] = constrained.summary()
        return result

    def release(self):
        self.local.release()


class EnvelopeReplayBackend(ReplayBackend):
    """A declared envelope agent's model (VERIFIER and PRACTICE_AUDITOR: the local auditor),
    loaded through bare_model's LocalBackend the way agent_wrapper.call_local loads it
    (agent_wrapper._load_qwen, sdpa pinned to the memory-efficient backend, one shot), in a
    process set up as the run's (final_models.verify_runtime's strict determinism in final
    mode). With `constraint`, the envelope constraint of the prompt's own agent
    (contract_decoding.for_prompt with the agent) rides beside the frozen decoding kwargs."""

    def prepare(self):
        if final_models.mode() == "final":
            final_models.verify_runtime()
        return self.local.prepare()


def _json_value(text):
    try:
        return True, json.loads(text)
    except (TypeError, ValueError):
        return False, None


def compare(rows, a, b, *, min_chunks=0):
    """Counts for one pair of paths over the prompts whose E prefill ran at least `min_chunks`
    chunks: byte-identical replies, replies that differ, replies parsing to equal JSON, and
    prompts with a failure or no reply on either side."""
    counts = dict.fromkeys(("prompts", "compared", "byte_identical", "differ", "json_equal", "failed_or_missing"), 0)
    for prompt_id, by_path in rows.items():
        chunks = max(int(((r.get("prefill") or {}).get("chunks")) or 0) for r in by_path.values())
        if chunks < min_chunks:
            continue
        counts["prompts"] += 1
        ra, rb = by_path.get(a), by_path.get(b)
        if not ra or not rb or ra.get("failure") or rb.get("failure") or not ra.get("reply") or not rb.get("reply"):
            counts["failed_or_missing"] += 1
            continue
        counts["compared"] += 1
        same = (ra["reply"]["sha256"], ra["reply"]["length_bytes"]) == (rb["reply"]["sha256"], rb["reply"]["length_bytes"])
        counts["byte_identical" if same else "differ"] += 1
        counts["json_equal"] += int(ra.get("json_equal_key") is not None and ra.get("json_equal_key") == rb.get("json_equal_key"))
    return counts


def run(prompts_path, out, *, paths=DEFAULT_PATHS, decision=None, max_new_tokens=None, backend=None,
        reader=None, run_id=None):
    """Replay every prompt through each path (see the module text); returns the measurement."""
    import bare_model
    out = Path(out)
    paths = list(paths)
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("--paths names each path once")
    declared = {name: path_record(name, decision) for name in paths}
    if decision is not None and not any(PATHS[name]["measurement"] for name in paths):
        raise ValueError("--decision is named only with a measurement path")
    prompts = load_prompts(prompts_path)
    models = {model_key(p) for p in prompts}
    if len(models) != 1:
        raise ValueError("a replay replays one model's prompts; this file holds %d" % len(models))
    (model_backend, _), = models
    envelope = model_backend != PRODUCER_BACKEND
    if envelope:
        # The envelope agents' prompts (extract --agents): replayed on their own model, loaded by
        # the run's own loader, under the run proper's setting only.
        backends = envelope_agents({p.get("agent") for p in prompts})
        if set(backends.values()) != {model_backend}:
            raise ValueError("a prompt's backend is not its agent's declared backend")
        if any(PATHS[name]["measurement"] for name in paths):
            raise ValueError("the envelope agents' prompts replay on sdpa and sdpa_constrained only")
    compact = {p["prompt_id"]: (not envelope) and is_compact(p["prompt"]) for p in prompts}
    if not envelope and any(PATHS[name].get("constraint") for name in paths) and not all(compact.values()):
        raise ValueError("a constrained path replays compact producer prompts only; %d prompt(s) carry no "
                         "canonical compact payload" % sum(1 for v in compact.values() if not v))
    context = bare_model.RunContext(out, run_id or ("replay-" + uuid.uuid4().hex[:12]))
    built = backend is None
    if reader is None:
        reader = (bare_model.resolve_reader(agent=sorted({p["agent"] for p in prompts})[0], checkpoint=bare_model.BASE)
                  if envelope else bare_model.resolve_reader(checkpoint=bare_model.TUNED))
    if envelope and built and reader["model_id"] != next(iter(prompts))["model_id"]:
        raise ValueError("the prompts were rendered for %s; the agent's local model is %s"
                         % (next(iter(prompts))["model_id"], reader["model_id"]))
    if built:
        backend = (EnvelopeReplayBackend if envelope else ReplayBackend)(reader, context)
    try:
        loaded = backend.prepare()
        limit = backend.max_context()
        rows, memory = {p["prompt_id"]: {} for p in prompts}, {}
        decoding = decoding_fields(reader)
        for name in paths:
            cuda, at_start = bare_model.start_gpu_memory()
            for prompt in prompts:
                allowance = int(max_new_tokens or prompt.get("max_new_tokens") or reader["max_new_tokens"])
                tokens = backend.count(prompt["prompt"])
                row = {"prompt_tokens": tokens, "max_new_tokens": allowance, "failure": None, "reply": None,
                       "output_tokens": None, "prefill": None}
                result, error = {}, ""
                if tokens + allowance > limit:
                    row["failure"] = error = "prompt_over_context"
                else:
                    try:
                        if PATHS[name].get("constraint") and envelope:
                            result = backend.generate(prompt["prompt"], declared[name], allowance, constraint=True,
                                                      agent=prompt["agent"]) or {}
                        elif PATHS[name].get("constraint"):
                            result = backend.generate(prompt["prompt"], declared[name], allowance, constraint=True) or {}
                        else:
                            result = backend.generate(prompt["prompt"], declared[name], allowance) or {}
                    except Exception as exc:
                        kind = final_models.generation_failure_kind(exc)
                        if kind is None:
                            raise
                        row["failure"] = error = kind
                        result = {}
                        gc.collect()
                        if cuda is not None:
                            cuda.empty_cache()
                text = result.get("text") if isinstance(result.get("text"), str) else None
                if text is not None:
                    parsed, value = _json_value(text)
                    row["reply"] = {"sha256": _sha(text), "length_bytes": len(text.encode("utf-8"))}
                    row["json_equal_key"] = _sha(json.dumps(value, sort_keys=True)) if parsed else None
                    row["output_tokens"] = result.get("output_tokens")
                    row["prefill"] = result.get("prefill")
                    if compact[prompt["prompt_id"]]:
                        reason = contract_reason(prompt["prompt"], text)
                        row["contract"] = {"valid": reason is None, "reason": reason}
                    elif envelope:
                        found = envelope_reasons(prompt["agent"], text, result.get("truncated"))
                        row["contract"] = {"valid": not found, "reason": "; ".join(found)[:160] or None}
                    if prompt.get("reference_reply_sha256"):
                        row["reference_identical"] = row["reply"]["sha256"] == prompt["reference_reply_sha256"]
                if result.get("decoding_constraint") is not None:
                    row["decoding_constraint"] = dict(result["decoding_constraint"])
                call = reply_records.write(
                    context, agent=AGENT_LABEL, backend=model_backend, model_id=reader["model_id"],
                    model_mode=reader["model_mode"], payload=prompt["prompt"], payload_form="rendered_prompt",
                    reply=text, ok=not error, error=error, decoding=dict(decoding, max_new_tokens=allowance),
                    sensitive=True, phase=PHASE, doc_id=prompt.get("doc_id") or "",
                    attention=result.get("attention") or declared[name], prefill=row["prefill"],
                    decoding_constraint=row.get("decoding_constraint"))
                if not call:
                    raise RuntimeError("the reply record for prompt %s, path %s could not be written"
                                       % (prompt["prompt_id"], name))
                row["call_id"] = call
                rows[prompt["prompt_id"]][name] = row
            memory[name] = bare_model.read_gpu_memory(cuda, at_start)
    finally:
        if built:
            backend.release()
    comparisons = {"%s_vs_%s" % pair: {"all": compare(rows, *pair), "three_chunks_or_more": compare(rows, *pair, min_chunks=THREE_CHUNKS)}
                   for pair in PAIRS if pair[0] in paths and pair[1] in paths}
    seconds = {name: [r[name]["prefill"]["prefill_seconds"] for r in rows.values()
                      if r[name].get("prefill") and isinstance(r[name]["prefill"].get("prefill_seconds"), (int, float))]
               for name in paths}
    sets = {p["prompt_id"]: p.get("set") or "records" for p in prompts}
    validity, reference, constrained = {}, {}, {}
    for name in paths:
        for prompt_id, by_path in rows.items():
            row, group = by_path[name], sets[prompt_id]
            if compact[prompt_id] or envelope:
                label = "contract_prompts" if envelope else "compact_prompts"
                counts = validity.setdefault(name, {}).setdefault(group, {label: 0, "replied": 0, "valid": 0, "reasons": {}})
                counts[label] += 1
                if row.get("contract") is not None:
                    counts["replied"] += 1
                    counts["valid"] += int(row["contract"]["valid"])
                    if row["contract"]["reason"]:
                        counts["reasons"][row["contract"]["reason"]] = counts["reasons"].get(row["contract"]["reason"], 0) + 1
            if "reference_identical" in row:
                counts = reference.setdefault(name, {}).setdefault(group, {"compared": 0, "byte_identical": 0, "differ": []})
                counts["compared"] += 1
                if row["reference_identical"]:
                    counts["byte_identical"] += 1
                else:
                    counts["differ"].append(prompt_id)
            if row.get("decoding_constraint") is not None:
                seen = row["decoding_constraint"]
                counts = constrained.setdefault(name, {}).setdefault(group, {"calls": 0, "steps": 0, "interventions": 0,
                                                                             "calls_with_intervention": 0, "dead_ends": 0})
                counts["calls"] += 1
                counts["steps"] += int(seen.get("steps") or 0)
                counts["interventions"] += int(seen.get("interventions") or 0)
                counts["calls_with_intervention"] += int(bool(seen.get("interventions")))
                counts["dead_ends"] += int(bool(seen.get("dead_end")))
    for by_path in rows.values():
        for row in by_path.values():
            row.pop("json_equal_key", None)
    result = {"schema": MEASUREMENT_SCHEMA, "run_id": context.run_id, "finished_at": _now(),
              "prompts": len(prompts), "paths": {name: declared[name] for name in paths},
              "decision": decision, "loaded": {k: loaded.get(k) for k in ("model_id", "digest", "checkpoint")},
              "gpu_memory": memory,
              "prefill_seconds": {name: {"measured": len(v), "total": round(sum(v), 6) if v else None,
                                         "max": max(v) if v else None} for name, v in seconds.items()},
              "failures": {name: sum(1 for r in rows.values() if r[name]["failure"]) for name in paths},
              "comparisons": comparisons,
              "validity": validity, "reference": reference, "constraint": constrained,
              "rows": [dict({"prompt_id": pid}, **{name: by_path[name] for name in paths}) for pid, by_path in rows.items()],
              "reads": "replay_prompts.json payloads only: no reply text, label or key"}
    _write_json(out / MEASUREMENT_FILE, result)
    return result


def is_compact(prompt):
    """True when a rendered prompt carries the compact producer's canonical payload."""
    import contract_decoding
    try:
        contract_decoding.payload_spans(prompt)
    except (RuntimeError, ValueError):
        return False
    return True


def contract_reason(prompt, text):
    """None when the reply passes compact_contracts.producer, unchanged, for the prompt's own
    request, else the validator's reason (contract_decoding.validate_rendered)."""
    import contract_decoding
    try:
        json.loads(text)
    except ValueError:
        return "not a JSON reply"
    try:
        return contract_decoding.validate_rendered(prompt, text)
    except RuntimeError as exc:
        return str(exc)[:80]


def envelope_reasons(agent, text, truncated):
    """[] when the reply holds the agent's envelope contract as a run judges it, else the
    reasons: agent_wrapper's parser and validator, unchanged, on a wrapper carrying the agent's
    contract, and run_task's completeness rule (a reply not known to have stopped on its own is
    not complete; `truncated` False only for a stop token)."""
    import agent_wrapper
    import contract_decoding
    wrapper = object.__new__(agent_wrapper.AgentWrapper)
    wrapper.name, wrapper.contract = agent, contract_decoding.declared_contracts()["contracts"][agent]
    parsed, missing = wrapper.parse_contract_output(text)
    found = list(missing) or ([] if parsed is not None else ["no JSON object found in output"])
    return found + (["response completeness not established"] if truncated is not False else [])


def decoding_fields(reader):
    import decoding_policy
    return dict(decoding_policy.usage_fields(reader["decoding"]))


def build_parser():
    """The two commands' parser. The ordinary final runner seals a replay pass's options against
    the `run` command's (tools/ordinary_final_run.py REPLAY_RUNNER_ARGS and REPLAY_SEALED_ARGS;
    a controller check holds them equal)."""
    parser = argparse.ArgumentParser(prog="replay_prompts.py", allow_abbrev=False,
                                     description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    ex = commands.add_parser("extract", allow_abbrev=False, help="replay_prompts.json from reply records (no model)")
    ex.add_argument("--records", action="append", default=[], help="an earlier run's audit/model_replies folder")
    ex.add_argument("--call-ids", default=None, help="a JSON list of the call ids to keep (or of objects with call_id)")
    ex.add_argument("--dev", action="store_true", help="add the validated DEV rows of checkpoint 168 with their frozen replies' digests")
    ex.add_argument("--agents", default=None,
                    help="comma-separated envelope agents (config/envelope_decoding.json) whose calls to keep instead of the producer's")
    ex.add_argument("--out", required=True)
    ex.add_argument("--min-chars", type=int, default=0)
    rn = commands.add_parser("run", allow_abbrev=False, help="replay the prompts through the paths (loads the model)")
    rn.add_argument("--prompts", required=True)
    rn.add_argument("--out", required=True)
    rn.add_argument("--paths", default=",".join(DEFAULT_PATHS))
    rn.add_argument("--decision", default=None, help="the recorded decision (D-NNN) that asks for the measurement paths")
    rn.add_argument("--max-new-tokens", type=int, default=None)
    return parser


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    args = build_parser().parse_args(argv)
    try:
        if args.command == "extract":
            value = extract(args.records, args.out, min_chars=args.min_chars, call_ids=_call_ids(args.call_ids),
                            dev=args.dev, agents={a for a in (args.agents or "").split(",") if a} or None)
            print(json.dumps({"prompt_count": value["prompt_count"], "sources": value["sources"]}, indent=2))
            return 0
        if Path(args.out).exists() and any(Path(args.out).iterdir()):
            raise ValueError("the output folder is not empty")
        result = run(args.prompts, args.out, paths=[p for p in args.paths.split(",") if p], decision=args.decision,
                     max_new_tokens=args.max_new_tokens)
        print(json.dumps(result["comparisons"], indent=2))
        return 0
    except Exception as exc:
        print("replay stopped: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
