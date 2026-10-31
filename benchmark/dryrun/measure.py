"""Free measurements on the chosen dry-run documents (loop plan S5 item 0.7, R24).

For every document of the choice file (choose.py), this command:

  1. builds it as a NON-development build (`--side development` with the cut inputs),
     through the adapter's own build, restricted to the chosen documents, with the main
     reading agent's own tokenizer as the token counter (token_counter.py: tokenizer files
     only, no model weights) and the model's context and the reading agent's output
     allowance; ContractNLI is built twice, `--parts span` and `--parts merged`;
  2. runs B2 (benchmark/baselines/python_only.py, no model call) on the built bundle;
  3. records per document: units (the pairing map's units), plans not asked
     (`ablation_not_asked`), words (section 5.6), whether it was cut, the B1 prompt tokens
     (system and user turns through the chat template, per item: the largest and the sum),
     and the memory upper bound for one B1 call (below), under B1's attention and, for
     reference, under eager attention.

The memory bound, in bytes, for one B1 call whose largest prompt over the document's items
is P tokens, T = P + the output allowance, with L layers, H attention heads, Hkv key-value
heads, d = hidden / H, hidden size h, MLP size m and vocabulary V, read from the model's own
config.json. Corrected by D-056 condition 8: B1 runs sdpa with the memory-efficient backend
pinned (benchmark/baselines/bare_model.py), and the model is prepared as the tuned producer
is (prepare_model_for_kbit_training), which casts every parameter that is not 4-bit to
float32, so the embeddings, the output layer, the norms and the biases, and with them the
hidden states and the key-value cache, are float32.

  weights      the 4-bit weights file on disk (stat; it holds the non-4-bit parameters in
               bf16) plus 2 bytes for each non-4-bit parameter, which float32 doubles:
               V * h for the embeddings and V * h for the output layer (one if the config
               ties them), 2 * h per layer and h for the norms, h + 2 * Hkv * d per layer for
               the q, k and v biases
  kv cache     2 * L * Hkv * d * T * 4                      (keys and values, float32)
  attention    sdpa, memory-efficient (B1): no T x T term; one layer's keys and values
               repeated to H heads before the kernel, 2 * H * d * T * 4, and the kernel's
               log-sum-exp, H * P * 4
               eager (reference only; the producer's training kernel, a measurement setting
               under D-063, when B1 and B3 both run sdpa): H * P * P * (4 + 4) + P * P * 4, one
               layer's float32 scores and their float32 softmax over the PROMPT (prefill is
               the largest square; a generated token's row is 1 x T), and the float32 mask
  activations  P * (4 * h + 3 * m) * 4                      (hidden states, q/k/v/o and the
               MLP's gate, up and product, float32, one layer, at prefill)
  dequantized  m * h * 2                                     (one 4-bit matrix dequantized
               to bf16 for a multi-token matmul)
  logits       V * 4                                         (generate keeps the last
               position's logits only)
  runtime      1 GiB                                         (CUDA context and allocator
               slack, an allowance, not a measurement)

It is an upper bound on these terms, not a measurement: L2's peak VRAM is the first one.
A document whose B1 bound passes LIMIT_BYTES (22 GB) is flagged; R24 replaces it by the
replacement the choice file lists, or runs it with the risk stated (the lead decides).

`recompute` reads a summary this command wrote and writes, per document, the bound it
recorded and the corrected sdpa and eager bounds from the same token counts (counts only).

Nothing is written outside --work and --summary (both under external/, gitignored).
Usage:
    py -3.12 -X utf8 benchmark/dryrun/measure.py --external <repo>/external
        --choice <choice.json> --work <folder> --summary <file> [--stand-in]
    py -3.12 -X utf8 benchmark/dryrun/measure.py recompute --summary <file> --out <file>
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(HERE), str(HERE.parent / "adapters"), str(HERE.parent / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import choose  # noqa: E402

LIMIT_BYTES = 22 * 10 ** 9
RUNTIME_ALLOWANCE = 1 << 30
PART_RULES = {"contractnli": ("span", "merged")}
STAND_IN_CONTEXT, STAND_IN_ALLOWANCE = 32768, 2048


class Only:
    """The adapter with its documents restricted to the chosen opaque ids: the build is
    the adapter's own, on fewer documents (ContractNLI still checks its frozen file)."""

    def __init__(self, adapter, wanted):
        self._adapter, self._wanted = adapter, set(wanted)

    def __getattr__(self, name):
        return getattr(self._adapter, name)

    def documents(self, records, options=None):
        return [d for d in self._adapter.documents(records, options)
                if d["document_id"] in self._wanted]


class StandIn:
    """One token per word, labelled: used only when the real tokenizer is not available."""
    label = "stand-in: one token per whitespace-separated word"

    @staticmethod
    def count(text):
        return len(text.split())

    @staticmethod
    def count_prompt(system, user):
        return len(system.split()) + len(user.split())


ATTENTIONS = ("sdpa", "eager")   # B1's kernel (D-056), and eager for reference
FLOAT32, BF16 = 4, 2


def non_4bit_parameters(dims: dict) -> int:
    """The parameters the 4-bit file holds outside its quantized layers: the embeddings and
    the output layer (one matrix when the config ties them), the norms, the q/k/v biases."""
    layers, heads, kv = dims["num_hidden_layers"], dims["num_attention_heads"], dims["num_key_value_heads"]
    hidden, vocab = dims["hidden_size"], dims["vocab_size"]
    head_dim = hidden // heads
    matrices = 1 if dims.get("tie_word_embeddings") else 2
    return (matrices * vocab * hidden + layers * 2 * hidden + hidden
            + layers * (hidden + 2 * kv * head_dim))


def memory_bound(prompt_tokens: int, allowance: int, dims: dict, attention: str = "sdpa") -> dict:
    """The upper bound for one B1 call (bytes; module docstring), under `attention`: sdpa
    with the memory-efficient backend (B1, D-056) or eager (reference)."""
    if attention not in ATTENTIONS:
        raise ValueError("attention is one of " + ", ".join(ATTENTIONS))
    p, t = int(prompt_tokens), int(prompt_tokens) + int(allowance)
    layers, heads, kv = dims["num_hidden_layers"], dims["num_attention_heads"], dims["num_key_value_heads"]
    hidden, mlp, vocab = dims["hidden_size"], dims["intermediate_size"], dims["vocab_size"]
    head_dim = hidden // heads
    if attention == "sdpa":
        attended = 2 * heads * head_dim * t * FLOAT32 + heads * p * FLOAT32
    else:
        attended = heads * p * p * (FLOAT32 + FLOAT32) + p * p * FLOAT32
    parts = {"weights": int(dims["weights_file_bytes"] or 0) + (FLOAT32 - BF16) * non_4bit_parameters(dims),
             "kv_cache": 2 * layers * kv * head_dim * t * FLOAT32,
             "attention": attended,
             "activations": p * (4 * hidden + 3 * mlp) * FLOAT32,
             "dequantized": mlp * hidden * BF16,
             "logits": vocab * FLOAT32,
             "runtime": RUNTIME_ALLOWANCE}
    total = sum(parts.values())
    return {"attention": attention, "prompt_tokens": p, "tokens": t, "bytes": parts,
            "total_bytes": total, "total_gb": round(total / 1e9, 2), "over_limit": total > LIMIT_BYTES}


MEMORY_FORMULA = ("weights file + 2*(2*V*h + 2*L*h + h + L*(h + 2*Hkv*d)) + 2*L*Hkv*d*T*4 "
                  "+ attention + P*(4h + 3m)*4 + m*h*2 + V*4 + 1 GiB; attention sdpa (B1, "
                  "D-056) 2*H*d*T*4 + H*P*4, eager (reference) H*P*P*8 + P*P*4; P = largest "
                  "B1 prompt, T = P + output allowance; float32 non-4-bit weights, "
                  "activations and KV cache (prepare_model_for_kbit_training)")


def recompute(summary_path, out_path) -> dict:
    """The corrected bounds for every document of a summary main() wrote, from the token
    counts and model dimensions it recorded: per document the bound it holds (the formula
    it was written with) and the corrected sdpa and eager bounds. Counts only."""
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    dims, allowance = summary["model_dimensions"] or _stand_in_dims(), int(summary["output_allowance"])
    rows = []
    for row in summary["documents"]:
        prompt = int(row["b1_prompt_tokens"]["max"])
        bounds = {a: memory_bound(prompt, allowance, dims, a) for a in ATTENTIONS}
        rows.append({"benchmark": row["benchmark"], "part_rule": row.get("part_rule"),
                     "document_id": row["document_id"], "role": row["role"], "band": row["band"],
                     "prompt_tokens": prompt, "tokens": prompt + allowance,
                     "recorded_bound_gb": row["memory_bound"]["total_gb"],
                     "recorded_over_limit": row["memory_bound"]["over_limit"],
                     "sdpa_bound_gb": bounds["sdpa"]["total_gb"], "sdpa_over_limit": bounds["sdpa"]["over_limit"],
                     "eager_bound_gb": bounds["eager"]["total_gb"],
                     "eager_over_limit": bounds["eager"]["over_limit"],
                     "sdpa_bytes": bounds["sdpa"]["bytes"], "eager_bytes": bounds["eager"]["bytes"]})
    result = {"source": Path(summary_path).name, "recorded_formula": summary.get("memory_formula"),
              "memory_formula": MEMORY_FORMULA, "limit_bytes": LIMIT_BYTES, "output_allowance": allowance,
              "documents": rows,
              "over_limit": {"recorded": sum(r["recorded_over_limit"] for r in rows),
                             "sdpa": sum(r["sdpa_over_limit"] for r in rows),
                             "eager": sum(r["eager_over_limit"] for r in rows)}}
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def b1_prompt_tokens(bundle, items, counter) -> dict:
    """The B1 prompt's tokens per item, rendered exactly as bare_model.py renders it."""
    import python_only
    from common import prompt
    spec = prompt.load_prompt(None)
    doc = python_only.load_bundle(bundle)["targets"][0]
    conventions = prompt.conventions_from_bundle(bundle)
    reference = prompt.reference_from_bundle(bundle)
    counts = []
    for item in items:
        bench = str(item["benchmark"]).lower()
        user = prompt.render_user(spec, bench, document=doc["text"], conventions=conventions,
                                  item=item, reference=reference)
        counts.append(counter.count_prompt(prompt.render_system(spec, bench), user))
    return {"items": len(counts), "max": max(counts), "sum": sum(counts),
            "document_tokens": counter.count(doc["text"])}


def measure_document(bench, bundle, items, parts_record, b2_out, counter, dims, allowance):
    """One built document: B2 run, units, plans not asked, words, B1 tokens, memory bound."""
    import python_only
    status = python_only.run(bundle, b2_out)
    doc_id = parts_record["document_id"]
    pairing = json.loads((Path(b2_out) / "audit" / "pairing_map.json").read_text(encoding="utf-8"))[doc_id]
    tokens = b1_prompt_tokens(bundle, items, counter)
    cut = parts_record.get("cut") or {}
    return {"benchmark": bench, "document_id": doc_id, "band": parts_record["length_band"],
            "words": parts_record["source_words"], "items": len(items),
            "units": len(pairing.get("units") or []),
            "plans_not_asked": pairing.get("ablation_not_asked_count", 0),
            "b2_model_calls": status["model_calls"],
            "b2_findings": status["documents"][doc_id]["findings"],
            "cut": bool(cut.get("cut")), "words_removed": cut.get("words_removed", 0),
            "b1_prompt_tokens": tokens,
            "memory_bound": memory_bound(tokens["max"], allowance, dims, "sdpa"),
            "memory_bound_eager": memory_bound(tokens["max"], allowance, dims, "eager")}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["recompute"]:
        again = argparse.ArgumentParser(prog="measure.py recompute",
                                        description="the corrected memory bounds of a written summary")
        again.add_argument("--summary", required=True)
        again.add_argument("--out", required=True)
        args = again.parse_args(argv[1:])
        result = recompute(args.summary, args.out)
        for row in result["documents"]:
            print("%-17s %-8s %s prompt=%d recorded=%.1f GB sdpa=%.1f GB eager=%.1f GB%s" % (
                row["benchmark"] + ("_" + row["part_rule"] if row["part_rule"] else ""), row["role"],
                row["document_id"], row["prompt_tokens"], row["recorded_bound_gb"], row["sdpa_bound_gb"],
                row["eager_bound_gb"], " OVER" if row["sdpa_over_limit"] else ""))
        return 0
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--external", required=True)
    parser.add_argument("--choice", required=True)
    parser.add_argument("--work", required=True, help="an empty folder for builds and B2 output")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--stand-in", action="store_true",
                        help="count with one token per word (labelled), not the real tokenizer")
    args = parser.parse_args(argv)
    import python_only
    from common import cli
    choice = json.loads(Path(args.choice).read_text(encoding="utf-8"))["documents"]
    allowance = int(python_only.pipeline_literal("PRODUCTION_MAX_TOKENS"))
    if args.stand_in:
        counter, counter_label, context = StandIn, StandIn.label, STAND_IN_CONTEXT
        dims, counter_file = None, None
    else:
        import token_counter as counter
        dims = counter.model_dimensions()
        counter_label = "real tokenizer: %s@%s (tokenizer files checked against base_hashes)" % (
            dims["model_id"], dims["revision"])
        context = dims["max_position_embeddings"]
        counter_file = str(HERE / "token_counter.py")   # its SHA-256 goes into parts.json
    work = Path(args.work)
    if work.exists() and any(work.iterdir()):
        raise SystemExit("the work folder is not empty: " + str(work))
    rows = []
    for bench in choose.ORDER:
        wanted = [c["document_id"] for c in choice if c["benchmark"] == bench]
        if not wanted:
            continue
        file_name, options = choose.INPUTS[bench]
        dev = Path(args.external) / bench / "dev"
        resolved = {k: str(dev / v) for k, v in options.items()}
        for rule in PART_RULES.get(bench, (None,)):
            label = bench + ("_" + rule if rule else "")
            build = work / label / "build"
            extra = dict(resolved, **({"parts": rule} if rule else {}))
            cli.build(Only(choose._adapter(bench), wanted), dev / file_name, build,
                      side="development", max_context=context, output_allowance=allowance,
                      token_counter=counter_file or counter, **extra)
            parts = {d["document_id"]: d for d in json.loads((build / "parts.json").read_text(
                encoding="utf-8"))["documents"]}
            items = json.loads((build / "items.json").read_text(encoding="utf-8"))["items"]
            for entry in [c for c in choice if c["benchmark"] == bench]:
                doc_id = entry["document_id"]
                mine = [i for i in items if i["document_id"] == doc_id]
                row = measure_document(bench, build / doc_id, mine, parts[doc_id],
                                       work / label / "b2" / doc_id, counter,
                                       dims or _stand_in_dims(), allowance)
                row.update(role=entry["role"], part_rule=rule, replacement=entry.get("replacement"))
                rows.append(row)
                print("%-17s %-8s %s %s words=%d units=%d not_asked=%d tokens=%d bound=%.1f GB%s" % (
                    label, entry["role"], row["band"], doc_id, row["words"], row["units"],
                    row["plans_not_asked"], row["b1_prompt_tokens"]["max"],
                    row["memory_bound"]["total_gb"], " OVER" if row["memory_bound"]["over_limit"] else ""))
    summary = {"counter": counter_label, "max_context": context, "output_allowance": allowance,
               "model_dimensions": dims, "limit_bytes": LIMIT_BYTES,
               "memory_formula": MEMORY_FORMULA,
               "documents": rows, "aggregates": aggregates(rows)}
    out = Path(args.summary)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


def _stand_in_dims():
    """Qwen2.5-7B's published shape, used only with --stand-in when config.json is absent."""
    return {"num_hidden_layers": 28, "num_attention_heads": 28, "num_key_value_heads": 4,
            "hidden_size": 3584, "intermediate_size": 18944, "vocab_size": 152064,
            "weights_file_bytes": None}


def aggregates(rows) -> dict:
    """Per benchmark (ContractNLI per part rule) and band: documents, and the median and
    total of units, plans not asked, words and largest B1 prompt tokens; the number over
    the memory limit."""
    out = {}
    for row in rows:
        if row["role"] != "chosen":
            continue
        key = row["benchmark"] + ("_" + row["part_rule"] if row["part_rule"] else "")
        group = out.setdefault(key, {}).setdefault(row["band"], [])
        group.append(row)
    result = {}
    for key, bands in out.items():
        for band, group in sorted(bands.items()):
            pick = lambda f: [f(r) for r in group]  # noqa: E731
            result.setdefault(key, {})[band] = {
                "documents": len(group),
                "units_total": sum(pick(lambda r: r["units"])),
                "plans_not_asked_total": sum(pick(lambda r: r["plans_not_asked"])),
                "plans_not_asked_median": statistics.median(pick(lambda r: r["plans_not_asked"])),
                "words_median": statistics.median(pick(lambda r: r["words"])),
                "b1_tokens_max_median": statistics.median(pick(lambda r: r["b1_prompt_tokens"]["max"])),
                "b1_tokens_sum_total": sum(pick(lambda r: r["b1_prompt_tokens"]["sum"])),
                "over_memory_limit": sum(pick(lambda r: int(r["memory_bound"]["over_limit"]))),
                "over_memory_limit_eager": sum(pick(lambda r: int(r["memory_bound_eager"]["over_limit"]))),
                "cut": sum(pick(lambda r: int(r["cut"])))}
    return result


if __name__ == "__main__":
    sys.exit(main())
