"""E's evidence on B3's own prompts (docs/loop/DECISIONS.md D-061 item 4): replay the producer
prompts an earlier B3 run rendered, standalone, through the measurement paths, one model load.

An evaluation tool, not a review and not an arm. Two commands:

  extract (no model)
      py -3.12 benchmark/baselines/replay_prompts.py extract --records <run>/audit/model_replies
          [--records <another run's folder> ...] --out replay_prompts.json [--min-chars N]
    Reads the reply records of one or more earlier runs (one JSON file per call, written by
    scripts/reply_records.py) and keeps every producer call (backend local_producer) whose
    rendered prompt text was saved (payload form rendered_prompt). It reads ONLY the payload
    and the call's identifiers (call id, agent, document id, the output allowance in its
    decoding record): never a reply, a label, an outcome or a key. A record of a sensitive run
    (hashes only) is refused, and so is any folder under benchmark/keys/. It writes
    replay_prompts.json: per prompt its source call id, agent, document id, the rendered
    prompt, its SHA-256 and the output allowance, and the source runs.

  run (loads the tuned producer once, through the loader B1's tuned checkpoint uses)
      py -3.12 benchmark/baselines/replay_prompts.py run --prompts replay_prompts.json --out <dir>
          [--paths e,one_shot,sdpa,e_repeat] [--decision D-NNN] [--max-new-tokens N]
    Runs every prompt through each path, in order, on the same resident model:
      e         eager, chunked at 512 tokens (E, D-061; a measurement path)
      one_shot  eager, prefilled in one shot (a measurement path)
      sdpa      sdpa pinned to the memory-efficient backend, one shot: the run proper's
                setting under D-063
      e_repeat  E again, for determinism (a measurement path)
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
    prompt and over the prompts of at least three chunks. Ids, hashes, counts and seconds only,
    never a prompt's or a reply's text.

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
}
DEFAULT_PATHS = ("e", "one_shot", "sdpa", "e_repeat")
PAIRS = (("e", "one_shot"), ("e", "e_repeat"), ("sdpa", "one_shot"), ("e", "sdpa"))
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


def extract(folders, out, *, min_chars=0):
    """replay_prompts.json from the reply records under `folders` (see the module text)."""
    prompts, sources = [], []
    for folder in folders:
        _refuse_keys(folder)
        rows = reply_records.records(folder)
        if not rows:
            raise ValueError("no reply records under " + str(folder))
        kept = 0
        for row in rows:
            if row.get("backend") != PRODUCER_BACKEND:
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
            prompts.append({"prompt_id": "p%04d" % (len(prompts) + 1), "source_call_id": row.get("call_id"),
                            "source_run_id": row.get("run_id"), "agent": row.get("agent"),
                            "doc_id": row.get("doc_id"), "max_new_tokens": allowance if type(allowance) is int else None,
                            "prompt_sha256": payload["sha256"], "prompt": text})
            kept += 1
        sources.append({"run_ids": sorted({str(r.get("run_id")) for r in rows}), "records": len(rows),
                        "producer_prompts": kept})
    if not prompts:
        raise ValueError("no producer prompt with its rendered text in the records given")
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

    def generate(self, prompt, attention, max_new_tokens):
        import torch
        tok, mdl = self.local._loaded()
        inputs = tok(prompt, return_tensors="pt", add_special_tokens=False).to(mdl.device)
        with torch.no_grad(), self.bare_model.b1_attention(mdl, implementation=attention["attention_implementation"]) as observe:
            observed = observe()
            out, measured = final_models.generate_with_prefill(
                mdl, inputs, max_new_tokens=max_new_tokens, decoding_kwargs=self.reader["decoding"]["kwargs"],
                prefill=self.bare_model.prefill_of(attention))
        start = int(inputs["input_ids"].shape[1])
        text = tok.decode(out[0][start:], skip_special_tokens=True)
        generated = int(out[0].shape[0]) - start
        del inputs, out
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return {"text": text, "output_tokens": generated, "attention": dict(attention, **observed), "prefill": measured}

    def release(self):
        self.local.release()


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
    context = bare_model.RunContext(out, run_id or ("replay-" + uuid.uuid4().hex[:12]))
    built = backend is None
    reader = reader or bare_model.resolve_reader(checkpoint=bare_model.TUNED)
    if built:
        backend = ReplayBackend(reader, context)
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
                call = reply_records.write(
                    context, agent=AGENT_LABEL, backend=PRODUCER_BACKEND, model_id=reader["model_id"],
                    model_mode=reader["model_mode"], payload=prompt["prompt"], payload_form="rendered_prompt",
                    reply=text, ok=not error, error=error, decoding=dict(decoding, max_new_tokens=allowance),
                    sensitive=True, phase=PHASE, doc_id=prompt.get("doc_id") or "",
                    attention=result.get("attention") or declared[name], prefill=row["prefill"])
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
              "rows": [dict({"prompt_id": pid}, **{name: by_path[name] for name in paths}) for pid, by_path in rows.items()],
              "reads": "replay_prompts.json payloads only: no reply text, label or key"}
    _write_json(out / MEASUREMENT_FILE, result)
    return result


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
    ex.add_argument("--records", action="append", required=True, help="an earlier run's audit/model_replies folder")
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
            value = extract(args.records, args.out, min_chars=args.min_chars)
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
