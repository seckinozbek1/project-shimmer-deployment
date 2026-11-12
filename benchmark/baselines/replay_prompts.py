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
    objects each carry a `set` label counts each prompt under its own set. --checkpoints
    tuned,base makes a ROLES file (D-S57): every producer prompt written once per checkpoint,
    adjacent, each row naming its `checkpoint` and `pair_of` (its source call id); the saved
    reply is the reference of the tuned row only (the checkpoint a final-mode run loaded).

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
    A file of envelope agents' prompts (one model a file) is replayed on their own model (the
    local auditor for VERIFIER and PRACTICE_AUDITOR, loaded by the run's loader in a process set
    up as the run's; the tuned producer for ARCHIVIST) on sdpa and sdpa_constrained
    only; sdpa_constrained carries the envelope constraint of each prompt's own agent, and every
    reply is judged by the agent's envelope validator and run_task's completeness rule, unchanged.
    A roles file loads every checkpoint it names once, before the first call (the tuned producer
    through final_models.resident, its base through bare_model.load_base_checkpoint, both held
    together), replays each row on its own checkpoint (a constrained path only when every row is
    a compact producer prompt), judges a compact prompt's reply by the compact validator and
    every other by its agent's own contract (the same validator and completeness rule), and
    writes `pairs`: per
    path and set, the pairs valid on both, on one only, on neither, and per checkpoint the
    failures, the replies that ran to their allowance and the output tokens. The rows of one
    prompt are adjacent, so a stop leaves every finished pair complete. No bound controller file
    reads the difference: the sealed pass counts one record per row per path, as before.

A G1 document-level judging prompts file (benchmark/baselines/doc_judge.py build) is read and
run by doc_judge.py through this tool's own `run` command and load_prompts, so the ordinary final
runner's sealed replay pass carries it unchanged (--paths sdpa only; reply text kept, since the
judge reads it afterwards). A prompt of its form `choice` (benchmark/baselines/choice_judge.py) is
decided by one forward pass, its probabilities on the reply record and no reply (D-S41). A
`judge-training-v1` file (benchmark/baselines/judge_train.py) rides the same pass: it trains an
adapter, then its questions run as such a file. A `producer-training-v1` file
(benchmark/baselines/producer_train.py) rides it the same way: it trains the producer's candidate
for checkpoint 168, then its test file runs here as a roles file with `tuned` and `candidate`; a
`producer-heldout-v1` file is its test-only held-out pass (no training; refused at assembly unless
docs/loop/HELDOUT_OPENINGS.md holds a committed opening, benchmark/baselines/producer_score.py). An
`auditor-training-session-v1` file (benchmark/baselines/auditor_train.py, D-S57 item 3) rides it
too: it trains the auditor backend's rule check, then asks its development questions.

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


def _checkpoint_names(checkpoints, readers=None):
    """The producer checkpoints a roles file replays each prompt on, in order (D-S57: the
    tuned producer against its own base on the other producer roles' saved prompts). Each
    named once, each one bare_model loads; with `readers` given (a caller that builds its own,
    the training pass's candidate on the base with its adapter), each one of theirs."""
    import bare_model
    names = list(checkpoints)
    allowed = list(readers) if readers is not None else list(bare_model.CHECKPOINTS)
    if not names or len(set(names)) != len(names) or any(n not in allowed for n in names):
        raise ValueError("--checkpoints names each checkpoint once, from " + ", ".join(allowed))
    return names


def extract(folders, out, *, min_chars=0, call_ids=None, dev=False, agents=None, checkpoints=None):
    """replay_prompts.json from the reply records under `folders` (only the calls `call_ids`
    names, when given) and, with `dev`, the DEV rows (see the module text). With `agents`, the
    calls of those declared envelope agents on their own backend instead of the producer's
    (DECODING-B's envelope constraint); --dev is the producer's and is refused with it. With
    `checkpoints` (a roles file), every producer prompt is written once per named checkpoint,
    the rows of one prompt next to each other, each carrying `checkpoint` and `pair_of` (its
    source call id); `run` replays each row on its own checkpoint and judges every reply by its
    agent's own contract."""
    prompts, sources = [], []
    wanted = set(call_ids) if call_ids is not None else None
    if not folders and not dev:
        raise ValueError("name reply record folders, --dev, or both")
    chosen = envelope_agents(agents) if agents else None
    if chosen is not None and dev:
        raise ValueError("--dev adds producer prompts; a replay file holds one model's prompts")
    names = _checkpoint_names(checkpoints) if checkpoints is not None else None
    if names is not None and (chosen is not None or dev):
        raise ValueError("--checkpoints replays the producer roles' saved prompts; not with --agents or --dev")
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
            for name in names or (None,):
                prompts.append({"prompt_id": "p%04d" % (len(prompts) + 1), "set": label,
                                "source_call_id": row.get("call_id"),
                                "source_run_id": row.get("run_id"), "agent": row.get("agent"),
                                "backend": row.get("backend"), "model_id": row.get("model_id"),
                                **({"envelope": True} if chosen is not None else {}),
                                **({"checkpoint": name, "pair_of": row.get("call_id")} if name else {}),
                                "doc_id": row.get("doc_id"), "max_new_tokens": allowance if type(allowance) is int else None,
                                "prompt_sha256": payload["sha256"],
                                # The saved reply is the checkpoint the run loaded (the tuned producer
                                # in final mode): a reference for that checkpoint's row only.
                                "reference_reply_sha256": (reference if isinstance(reference, str) and (
                                    name is None or (name == "tuned" and row.get("model_mode") == "final")) else None),
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


def _doc_judge():
    import doc_judge
    return doc_judge


def _embed_records():
    import embed_records
    return embed_records


def is_embed_records(path):
    """True when the file is an `embed-records-v1` file (embed_records.py build, D-507): the same sealed pass,
    which embeds the records with bge-m3 and writes vectors. Sniffed from the file's head, since the file
    may be a hundred megabytes and every other reader here parses the whole of it."""
    try:
        return _embed_records().is_prompts_path(path)
    except ImportError:
        return False


def _negotiation_b1():
    import negotiation_b1
    return negotiation_b1


def is_negotiation(path):
    """True when the file is a negotiation B1 prompts file (negotiation_b1.py build, D-S102 item 8),
    which this tool's `run` hands to negotiation_b1.run and load_prompts to its load_prompts."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    try:
        return _negotiation_b1().is_prompts_file(value)
    except ImportError:
        return False


def is_doc_judge(path):
    """True when the file is a G1 document-level judging prompts file (doc_judge.py build),
    which this tool's `run` hands to doc_judge.run and load_prompts to doc_judge.load_prompts:
    the one replay pass the ordinary final runner seals carries either kind."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    try:
        tool = _doc_judge()
    except ImportError:
        # An ordinary replay never needs doc_judge: a G1 file then fails as an unknown schema.
        return False
    return tool.is_prompts_file(value)


def _judge_train():
    import judge_train
    return judge_train


def is_judge_training(path):
    """True when the file is a `judge-training-v1` file (judge_train.py assemble): the same sealed
    pass, which trains an adapter and then asks that file's questions (D-S42 item 2)."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(value, dict) and value.get("schema") in ("judge-training-v1", "judge-training-session-v1")


def _producer_train():
    import producer_train
    return producer_train


def is_producer_training(path):
    """True when the file is a `producer-training-v1` file (producer_train.py assemble): the same
    sealed pass, which trains the producer's candidate and then asks its test (D-S57 item 3)."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(value, dict) and value.get("schema") in ("producer-training-v1", "producer-heldout-v1")


def _producer_heldout(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("schema") == "producer-heldout-v1"
    except (OSError, ValueError, AttributeError):
        return False


def _auditor_train():
    import auditor_train
    return auditor_train


def is_auditor_training(path):
    """True when the file is an `auditor-training-session-v1` file (auditor_train.py session): the
    same sealed pass, which trains the auditor backend's rule check and then asks its development
    questions (D-S57 item 3)."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(value, dict) and value.get("schema") in ("auditor-training-v1", "auditor-training-session-v1")


def load_prompts(path):
    """The prompts of a replay_prompts.json, each checked against its own SHA-256 (a G1 file
    by doc_judge.load_prompts, which re-renders every prompt from the file's own template)."""
    if is_embed_records(path):
        return _embed_records().load_prompts(path)
    if is_producer_training(path):
        return (_producer_train().load_heldout_prompts(path) if _producer_heldout(path)
                else _producer_train().load_prompts(path))
    if is_auditor_training(path):
        return _auditor_train().load_prompts(path)
    if is_judge_training(path):
        return _judge_train().load_prompts(path)
    if is_doc_judge(path):
        return _doc_judge().load_prompts(path)
    if is_negotiation(path):
        return _negotiation_b1().load_prompts(path)
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
    # The envelope agents' prompts (extract --agents): each prompt names its agent and backend.
    envelope = any(p.get("envelope") is True for p in prompts)
    if envelope and not all(p.get("envelope") is True for p in prompts):
        raise ValueError("a replay file holds envelope agents' prompts or producer prompts, not both")
    if envelope:
        # Replayed on their own model, loaded by the run's own loader (the tuned producer for a
        # local_producer agent, the agent's local model otherwise), under the run proper's
        # setting only.
        backends = envelope_agents({p.get("agent") for p in prompts})
        if set(backends.values()) != {model_backend} or any(p.get("backend") != model_backend for p in prompts):
            raise ValueError("a prompt's backend is not its agent's declared backend")
        if any(PATHS[name]["measurement"] for name in paths):
            raise ValueError("the envelope agents' prompts replay on sdpa and sdpa_constrained only")
    # A roles file (extract --checkpoints): each row replays on its own producer checkpoint,
    # every checkpoint loaded once before the first call and all of them held to the end, and
    # each reply is judged by its agent's own contract.
    roles = any("checkpoint" in p for p in prompts)
    if roles:
        if envelope or model_backend != PRODUCER_BACKEND or not all("checkpoint" in p for p in prompts):
            raise ValueError("a roles file holds producer prompts, every row naming its checkpoint")
        checkpoints = _checkpoint_names(dict.fromkeys(p["checkpoint"] for p in prompts),
                                        reader if isinstance(reader, dict) and "decoding" not in reader else None)
    else:
        checkpoints = [None]
    compact = {p["prompt_id"]: (not envelope) and is_compact(p["prompt"]) for p in prompts}
    if roles:
        # A compact producer prompt is judged by the compact validator, every other by its
        # agent's own contract, which it must have.
        unknown = sorted({p["agent"] for p in prompts if not compact[p["prompt_id"]]} - _declared_contract_agents())
        if unknown:
            raise ValueError("a roles file names an agent with no contract: " + ", ".join(unknown))
    if not envelope and any(PATHS[name].get("constraint") for name in paths) and not all(compact.values()):
        raise ValueError("a constrained path replays compact producer prompts only; %d prompt(s) carry no "
                         "canonical compact payload" % sum(1 for v in compact.values() if not v))
    context = bare_model.RunContext(out, run_id or ("replay-" + uuid.uuid4().hex[:12]))
    built = backend is None
    auditor = envelope and model_backend != PRODUCER_BACKEND
    if roles:
        readers = dict(reader) if isinstance(reader, dict) and "decoding" not in reader and set(reader) == set(checkpoints) else (
            {c: bare_model.resolve_reader(checkpoint=c) for c in checkpoints} if reader is None else None)
        if readers is None:
            raise ValueError("a roles file is read with one reader per checkpoint")
        backends = dict(backend) if not built else {c: ReplayBackend(readers[c], context) for c in checkpoints}
        if set(backends) != set(checkpoints):
            raise ValueError("a roles file is replayed with one backend per checkpoint")
        reader = readers[checkpoints[0]]
    else:
        if reader is None:
            reader = (bare_model.resolve_reader(agent=sorted({p["agent"] for p in prompts})[0], checkpoint=bare_model.BASE)
                      if auditor else bare_model.resolve_reader(checkpoint=bare_model.TUNED))
        if auditor and built and reader["model_id"] != next(iter(prompts))["model_id"]:
            raise ValueError("the prompts were rendered for %s; the agent's local model is %s"
                             % (next(iter(prompts))["model_id"], reader["model_id"]))
        if built:
            backend = (EnvelopeReplayBackend if auditor else ReplayBackend)(reader, context)
        readers, backends = {None: reader}, {None: backend}
    prepared = []
    try:
        loads = {}
        for c in checkpoints:
            loads[c] = backends[c].prepare()
            prepared.append(c)
        loaded = loads[checkpoints[0]]
        limit = min(backends[c].max_context() for c in checkpoints)
        rows, memory = {p["prompt_id"]: {} for p in prompts}, {}
        for name in paths:
            cuda, at_start = bare_model.start_gpu_memory()
            for prompt in prompts:
                backend, reader = backends[prompt.get("checkpoint")], readers[prompt.get("checkpoint")]
                decoding = decoding_fields(reader)
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
                    elif envelope or roles:
                        found = envelope_reasons(prompt["agent"], text, result.get("truncated"))
                        row["contract"] = {"valid": not found, "reason": "; ".join(found)[:160] or None}
                    if roles:
                        row["truncated"] = result.get("truncated")
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
                if roles:
                    row["checkpoint"] = prompt["checkpoint"]
                rows[prompt["prompt_id"]][name] = row
            memory[name] = bare_model.read_gpu_memory(cuda, at_start)
    finally:
        if built:
            for c in reversed(prepared or checkpoints[:1]):
                backends[c].release()
    comparisons = {"%s_vs_%s" % pair: {"all": compare(rows, *pair), "three_chunks_or_more": compare(rows, *pair, min_chunks=THREE_CHUNKS)}
                   for pair in PAIRS if pair[0] in paths and pair[1] in paths}
    seconds = {name: [r[name]["prefill"]["prefill_seconds"] for r in rows.values()
                      if r[name].get("prefill") and isinstance(r[name]["prefill"].get("prefill_seconds"), (int, float))]
               for name in paths}
    sets = {p["prompt_id"]: (p.get("set") or "records") + ("@" + p["checkpoint"] if roles else "") for p in prompts}
    validity, reference, constrained = {}, {}, {}
    for name in paths:
        for prompt_id, by_path in rows.items():
            row, group = by_path[name], sets[prompt_id]
            if compact[prompt_id] or envelope or roles:
                label = "contract_prompts" if envelope or roles else "compact_prompts"
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
    paired = role_pairs(prompts, rows, paths, checkpoints) if roles else None
    for by_path in rows.values():
        for row in by_path.values():
            row.pop("json_equal_key", None)
    result = {"schema": MEASUREMENT_SCHEMA, "run_id": context.run_id, "finished_at": _now(),
              "prompts": len(prompts), "paths": {name: declared[name] for name in paths},
              "decision": decision, "loaded": {k: loaded.get(k) for k in ("model_id", "digest", "checkpoint")},
              **({"loaded_checkpoints": {c: {k: loads[c].get(k) for k in ("model_id", "digest", "checkpoint")}
                                         for c in checkpoints}, "pairs": paired} if roles else {}),
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


def _declared_contract_agents():
    import contract_decoding
    return set(contract_decoding.declared_contracts()["contracts"])


def role_pairs(prompts, rows, paths, checkpoints):
    """A roles file's paired counts, per path and per set (an agent's prompts), over the
    prompts replayed on every checkpoint: for the first two checkpoints (a, b), how many pairs
    are valid on both, on a only, on b only, on neither (the discordant counts a sign test
    reads), byte-identical and parsing to equal JSON; per checkpoint the failures, the replies
    that ran to their allowance, and the output tokens. Counts only."""
    groups = {}
    for p in prompts:
        groups.setdefault(p["pair_of"], {})[p["checkpoint"]] = p
    a, b = (checkpoints + [None])[:2]
    result = {}
    for name in paths:
        for members in groups.values():
            if set(members) != set(checkpoints):
                continue
            label = members[a].get("set") or "records"
            counts = result.setdefault(name, {}).setdefault(label, dict(
                checkpoints=[a, b], pairs=0, both_valid=0, a_only_valid=0, b_only_valid=0, neither_valid=0,
                byte_identical=0, json_equal=0,
                failures={c: 0 for c in checkpoints}, truncated={c: 0 for c in checkpoints},
                output_tokens={c: 0 for c in checkpoints}))
            seen = {c: rows[members[c]["prompt_id"]][name] for c in checkpoints}
            counts["pairs"] += 1
            for c, row in seen.items():
                counts["failures"][c] += int(bool(row.get("failure")))
                counts["truncated"][c] += int(row.get("truncated") is not False and row.get("reply") is not None)
                counts["output_tokens"][c] += int(row.get("output_tokens") or 0)
            if b is None:
                continue
            va, vb = (bool((seen[c].get("contract") or {}).get("valid")) for c in (a, b))
            counts[("both_valid" if vb else "a_only_valid") if va else ("b_only_valid" if vb else "neither_valid")] += 1
            ra, rb = seen[a].get("reply"), seen[b].get("reply")
            counts["byte_identical"] += int(bool(ra and rb and ra == rb))
            counts["json_equal"] += int(seen[a].get("json_equal_key") is not None
                                        and seen[a].get("json_equal_key") == seen[b].get("json_equal_key"))
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
    ex.add_argument("--checkpoints", default=None,
                    help="comma-separated producer checkpoints (tuned, base): a roles file, each prompt once per checkpoint")
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
                            dev=args.dev, agents={a for a in (args.agents or "").split(",") if a} or None,
                            checkpoints=[c for c in args.checkpoints.split(",") if c] if args.checkpoints else None)
            print(json.dumps({"prompt_count": value["prompt_count"], "sources": value["sources"]}, indent=2))
            return 0
        if Path(args.out).exists() and any(Path(args.out).iterdir()):
            raise ValueError("the output folder is not empty")
        if is_embed_records(args.prompts):
            # D-507: the same sealed pass, the records embedded with bge-m3 (embed_records.py).
            if [p for p in args.paths.split(",") if p] != ["sdpa"] or args.decision or args.max_new_tokens:
                raise ValueError("an embedding pass runs the sdpa path alone, no decision, no token allowance")
            result = _embed_records().run(args.prompts, args.out)
            print(json.dumps({"prompts": result["prompts"], "failures": result["failures"], "seconds": result["seconds"]}, indent=2))
            return 0
        if is_producer_training(args.prompts):
            # D-S57 item 3: the producer's candidate trained, then its test (producer_train.py).
            runner = _producer_train().heldout_run if _producer_heldout(args.prompts) else _producer_train().run
            result = runner(args.prompts, args.out, paths=[p for p in args.paths.split(",") if p],
                            decision=args.decision, max_new_tokens=args.max_new_tokens)
            print(json.dumps({"prompts": result["prompts"], "failures": result["failures"]}, indent=2))
            return 0
        if is_auditor_training(args.prompts):
            # D-S57 item 3: the same sealed pass, the auditor's training and its questions (auditor_train.py).
            result = _auditor_train().run(args.prompts, args.out, paths=[p for p in args.paths.split(",") if p],
                                          decision=args.decision, max_new_tokens=args.max_new_tokens)
            print(json.dumps({"prompts": result["prompts"], "failures": result["failures"],
                              "seconds": result["seconds"]}, indent=2))
            return 0
        if is_judge_training(args.prompts):
            # T: the same sealed pass, its own training and then its questions (judge_train.py).
            result = _judge_train().run(args.prompts, args.out, paths=[p for p in args.paths.split(",") if p],
                                        decision=args.decision, max_new_tokens=args.max_new_tokens)
            print(json.dumps({"prompts": result["prompts"], "failures": result["failures"],
                              "seconds": result["seconds"]}, indent=2))
            return 0
        if is_negotiation(args.prompts):
            # D-S102 item 8: the same sealed pass, B1 on the negotiation features (negotiation_b1.py).
            if [p for p in args.paths.split(",") if p] != ["sdpa"] or args.decision or args.max_new_tokens:
                raise ValueError("a negotiation B1 pass runs the sdpa path alone, each prompt's own allowance, no decision")
            result = _negotiation_b1().run(args.prompts, args.out)
            print(json.dumps({"prompts": result["prompts"], "seconds": result["seconds"]}, indent=2))
            return 0
        if is_doc_judge(args.prompts):
            # G1: the same sealed pass, its own judging run (benchmark/baselines/doc_judge.py).
            result = _doc_judge().run(args.prompts, args.out, paths=[p for p in args.paths.split(",") if p],
                                      decision=args.decision, max_new_tokens=args.max_new_tokens)
            print(json.dumps({"prompts": result["prompts"], "failures": result["failures"],
                              "seconds": result["seconds"]}, indent=2))
            return 0
        result = run(args.prompts, args.out, paths=[p for p in args.paths.split(",") if p], decision=args.decision,
                     max_new_tokens=args.max_new_tokens)
        print(json.dumps(result["comparisons"], indent=2))
        return 0
    except Exception as exc:
        print("replay stopped: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
