"""B1, the bare-model arm: the main reading agent's model, one fixed prompt per item, no pipeline.

An evaluation tool, not a review. For one test bundle and the item table the adapter
wrote beside it (``items.json``: item_id, document_id, rule_id, benchmark; no gold),
it sends the preregistered prompt (``b1_prompt.json``, from
docs/benchmarks/PREREGISTRATION.md section 5.4) once per item, with the document as
it stands in the bundle (already cut by the adapter, section 5.3), every convention
of the bundle, and the fixed line ``None.`` for reference material. It writes:

  <out>/audit/model_replies/   one record per call, through reply_records.write (the
                               S1 Part 4 write path every pipeline backend uses), with
                               this tool's own run context
  <out>/labels/<item_id>.json  one typed label per item; a reply that does not parse,
                               or whose label is not in the list, is ABSTAIN
  <out>/b1_summary.json        counts and the parse rate per benchmark

The model is read at run time from the configuration the pipeline uses: the agent's
backend from the pipeline's local profile table and config/local_models.json (both
read as data, the pipeline is never imported), its checkpoint through final_models
in final mode, and its decoding policy through scripts/decoding_policy.py. The output
allowance is the pipeline's PROCESSOR budget (PRODUCTION_MAX_TOKENS), also read as
data, unless --max-new-tokens overrides it (the value used is recorded either way).

The cut rule of section 5.3 is applied by the adapter before bundling; its two
functions live here (``cut_budget``, ``cut_document``) with an injected token
counter, because the budget depends on this prompt with an empty document.

Usage (loads a local model; for the rented machine, never this laptop):
    py -3.12 benchmark/baselines/bare_model.py --bundle <bundle> --items <items.json> --out <dir>
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "scripts"
for _p in (str(SCRIPTS), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import decoding_policy  # noqa: E402
import final_models  # noqa: E402
import finding_record  # noqa: E402
import python_only  # noqa: E402  the bundle loader shared with B2
import reply_records  # noqa: E402

ARM = "B1"
AGENT_LABEL = "B1_BARE_MODEL"
BASELINE_TEXT = "BASELINE B1 (bare model): one fixed prompt per item, no pipeline. This is not a review."
PROMPT_PATH = HERE / "b1_prompt.json"
READING_AGENT = "PROCESSOR"
PIPELINE_SOURCE = SCRIPTS / "pipeline.py"
_SLOT = re.compile(r"\{(document|conventions|item_id|rule_id|question|label_lines|undecided_label)\}")
_FENCE = re.compile(r"^\s*```[^`\s]*\s*$")


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# the prompt


def load_prompt(path=PROMPT_PATH):
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("system", "user_template", "convention_line", "benchmarks"):
        if key not in spec:
            raise ValueError("b1_prompt.json lacks " + key)
    for name, bench in spec["benchmarks"].items():
        names = label_names(bench)
        if _norm_label(bench["undecided"]) not in {_norm_label(n) for n in names}:
            raise ValueError("the undecided label of %s is not one of its labels" % name)
    return spec


def label_names(bench):
    """The label names: each label line's text before its first colon."""
    return [line.split(":", 1)[0].strip() for line in bench["labels"]]


def conventions_block(registry):
    """Every convention of the bundle, one per line with its rule id (the operator's own
    id where the heading carries one, else the registry id)."""
    lines = []
    for c in registry.get("conventions", []):
        rule_id = finding_record.source_rule_id_for(c.get("id"), registry) or c.get("id")
        text = " ".join(str(c.get("rule") or "").split())
        lines.append((rule_id, text))
    return lines


def render_user(spec, bench_key, *, document, conventions, item):
    bench = spec["benchmarks"][bench_key]
    values = {
        "document": document,
        "conventions": "\n".join(spec["convention_line"].replace("{rule_id}", rid)
                                 .replace("{rule_text}", text) for rid, text in conventions),
        "item_id": item["item_id"],
        "rule_id": item["rule_id"],
        "question": bench["question"],
        "label_lines": "\n".join(bench["labels"]),
        "undecided_label": bench["undecided"],
    }
    # One pass: a filled slot is never read again, so braces in the document stay text.
    return _SLOT.sub(lambda m: values[m.group(1)], spec["user_template"])


# ---------------------------------------------------------------------------
# the parser (section 5.4)


def _norm_label(value):
    text = str(value).lower().strip()
    if text.endswith("(undecided)"):
        text = text[: -len("(undecided)")]
    text = text.split(":", 1)[0].strip()
    return text.replace("_", " ")


def _last_balanced_object(text):
    """The last balanced {...}: from each closing brace, last first, scan back for the
    brace that balances it; the first closing brace that has one wins."""
    for end in range(len(text) - 1, -1, -1):
        if text[end] != "}":
            continue
        depth = 0
        for start in range(end, -1, -1):
            if text[start] == "}":
                depth += 1
            elif text[start] == "{":
                depth -= 1
                if depth == 0:
                    return text[start:end + 1]
    return None


def parse_reply(reply, bench, item_id=None):
    """{parsed, label, evidence, reason, reply_item_id, item_id_matches, failure}."""
    out = {"parsed": False, "label": None, "evidence": None, "reason": None,
           "reply_item_id": None, "item_id_matches": None, "failure": None}
    if not isinstance(reply, str) or not reply.strip():
        out["failure"] = "empty_reply"
        return out
    kept = "\n".join(line for line in reply.splitlines() if not _FENCE.match(line))
    candidate = _last_balanced_object(kept)
    if candidate is None:
        out["failure"] = "no_json_object"
        return out
    try:
        obj = json.loads(candidate)
    except ValueError:
        out["failure"] = "json_invalid"
        return out
    if not isinstance(obj, dict) or not isinstance(obj.get("label"), str):
        out["failure"] = "no_label"
        return out
    wanted = _norm_label(obj["label"])
    match = next((name for name in label_names(bench) if _norm_label(name) == wanted), None)
    out["reply_item_id"] = obj.get("item_id")
    out["item_id_matches"] = (str(obj.get("item_id")) == str(item_id)) if item_id else None
    out["evidence"] = obj.get("evidence") if isinstance(obj.get("evidence"), str) else None
    out["reason"] = obj.get("reason") if isinstance(obj.get("reason"), str) else None
    if match is None:
        out["failure"] = "label_not_in_list"
        return out
    out["parsed"] = True
    out["label"] = match
    return out


# ---------------------------------------------------------------------------
# the cut rule (section 5.3), with an injected token counter


def words(text):
    return len(str(text).split())


def cut_note(remaining, total):
    return "[Document cut: the remaining %d of %d words are not shown.]" % (remaining, total)


def cut_budget(max_context, prompt_tokens_empty_document, output_allowance):
    """Context minus the prompt with an empty document (the largest over the document's
    items) minus the output allowance minus 32."""
    return int(max_context) - int(prompt_tokens_empty_document) - int(output_allowance) - 32


def prompt_overhead(spec, items, conventions, count_prompt):
    """The token count of this prompt with an empty document, the largest over `items`.
    count_prompt(system, user) -> int counts the whole prompt as the model sees it."""
    return max(count_prompt(spec["system"], render_user(
        spec, str(item["benchmark"]).lower(), document="", conventions=conventions, item=item))
        for item in items)


def cut_document(text, budget, count):
    """(text, info). Whole blank-line paragraphs from the start while they fit, the cut
    line appended to the last one kept; a first paragraph that alone does not fit is cut
    at the last whitespace that fits. count(text) -> int, the model's own tokenizer."""
    total = words(text)
    if count(text) <= budget:
        return text, {"cut": False, "words_total": total, "words_removed": 0, "paragraphs_kept": None}
    ends = [m.start() for m in re.finditer(r"\n(?:[ \t]*\n)+", text)] + [len(text)]

    def candidate(prefix):
        removed = total - words(prefix)
        return prefix.rstrip() + "\n" + cut_note(removed, total), removed

    kept, kept_count = None, 0
    for k, end in enumerate(ends, start=1):
        cand, removed = candidate(text[:end])
        if count(cand) > budget:
            break
        kept, kept_count = (cand, removed), k
    if kept is not None:
        return kept[0], {"cut": True, "words_total": total, "words_removed": kept[1],
                         "paragraphs_kept": kept_count}
    first = text[:ends[0]]
    cuts = [m.start() for m in re.finditer(r"\s", first)]
    lo, hi, best = 0, len(cuts) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        cand, removed = candidate(first[:cuts[mid]])
        if count(cand) <= budget:
            best, lo = (cand, removed), mid + 1
        else:
            hi = mid - 1
    if best is None:
        raise ValueError("the budget does not hold even the cut line")
    return best[0], {"cut": True, "words_total": total, "words_removed": best[1], "paragraphs_kept": 0}


# ---------------------------------------------------------------------------
# the model, read from the pipeline's own configuration


def pipeline_literal(name, source=PIPELINE_SOURCE):
    """The first top-level assignment of `name` in the pipeline source whose value is a
    literal, read with ast (the pipeline is never imported)."""
    tree = ast.parse(Path(source).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            try:
                return ast.literal_eval(node.value)
            except ValueError:
                continue
    raise KeyError(name + " is not a literal assignment in " + Path(source).name)


def resolve_reader(root=ROOT, *, agent=READING_AGENT, profile="local", max_new_tokens=None):
    """The main reading agent's backend, model, decoding policy and output allowance."""
    root = Path(root)
    registry = json.loads((root / "config" / "agent_registry.json").read_text(encoding="utf-8"))
    entry = registry["agents"][agent]
    backend, model_id = entry["backend"], entry["model"]
    sources = {"registry": "config/agent_registry.json"}
    if profile == "local":
        backend, model_id = pipeline_literal("_LOCAL_PROFILE", root / "scripts" / "pipeline.py")[agent]
        try:
            chosen = json.loads((root / "config" / "local_models.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            chosen = {}
        key = {"local_producer": "active_producer", "local_auditor": "active_auditor"}.get(backend)
        if key and str(chosen.get(key) or "").strip():
            model_id = chosen[key].strip()
            sources["model"] = "config/local_models.json " + key
    if backend not in decoding_policy.LOCAL_BACKENDS:
        raise ValueError("the reading agent's backend %r is not a local backend" % backend)
    decoding = decoding_policy.policy(backend, root)
    declared, _ = decoding_policy.declaration(root)
    role = declared["backends"][backend].get("role")
    mode = final_models.mode()
    if mode == "final" and backend == "local_producer":
        model_id = final_models.specification("producer", root)["model_id"]
        sources["model"] = "config/final_models.json producer"
    allowance = (int(max_new_tokens) if max_new_tokens is not None
                 else int(pipeline_literal("PRODUCTION_MAX_TOKENS", root / "scripts" / "pipeline.py")))
    return {"agent": agent, "backend": backend, "model_id": model_id, "model_mode": mode,
            "role": role, "decoding": decoding, "max_new_tokens": allowance,
            "max_new_tokens_source": "argument" if max_new_tokens is not None
            else "pipeline PRODUCTION_MAX_TOKENS", "sources": sources}


class LocalBackend:
    """The model, loaded and called the way agent_wrapper.call_local loads and calls it:
    final mode through final_models.resident, base mode through the shared loader, the
    model's own chat template with a system and a user turn, the frozen decoding kwargs.
    Imported lazily: nothing here loads before the first call."""

    def __init__(self, reader, run_context):
        self.reader, self.run_context = reader, run_context
        self._tok = self._mdl = None

    def _load(self):
        if self._tok is None:
            if self.reader["model_mode"] == "final" and self.reader["backend"] == "local_producer":
                final_models.verify_runtime()
                self._tok, self._mdl = final_models.resident("producer", self.run_context)
            else:
                import agent_wrapper
                self._tok, self._mdl = agent_wrapper._load_qwen(self.reader["model_id"])
        return self._tok, self._mdl

    def _render(self, system, user):
        tok, _ = self._load()
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    def count_prompt(self, system, user):
        tok, _ = self._load()
        return len(tok(self._render(system, user), add_special_tokens=False)["input_ids"])

    def count_text(self, text):
        tok, _ = self._load()
        return len(tok(text, add_special_tokens=False)["input_ids"])

    def max_context(self):
        _, mdl = self._load()
        return int(mdl.config.max_position_embeddings)

    def generate(self, system, user, max_new_tokens):
        import torch
        tok, mdl = self._load()
        prompt = self._render(system, user)
        inputs = tok(prompt, return_tensors="pt", add_special_tokens=False).to(mdl.device)
        with torch.no_grad():
            out = mdl.generate(**inputs, max_new_tokens=max_new_tokens,
                               **self.reader["decoding"]["kwargs"])
        start = int(inputs["input_ids"].shape[1])
        text = tok.decode(out[0][start:], skip_special_tokens=True)
        del inputs, out
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return {"text": text, "payload": prompt, "form": "rendered_prompt"}


# ---------------------------------------------------------------------------
# the run


def load_items(path, document_id):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("items") if isinstance(data, dict) else data
    items = [r for r in rows or [] if str(r.get("document_id")) == str(document_id)]
    for r in items:
        for key in ("item_id", "rule_id", "benchmark"):
            if not r.get(key):
                raise ValueError("an item lacks " + key)
    return sorted(items, key=lambda r: str(r["item_id"]))


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(bundle, items_path, out, *, backend=None, reader=None, prompt_path=PROMPT_PATH,
        run_id=None):
    """Run B1 on one bundle. `backend` needs generate(system, user, max_new_tokens) ->
    {text, payload, form}; None builds the LocalBackend (a real model load)."""
    out = Path(out)
    spec = load_prompt(prompt_path)
    data = python_only.load_bundle(bundle)
    if len(data["targets"]) != 1:
        raise ValueError("a benchmark bundle names exactly one document under review")
    if data["grounding"] or data["prior"]:
        raise ValueError("the preregistered prompt shows no reference material; this bundle declares some")
    doc = data["targets"][0]
    items = load_items(items_path, doc["id"])
    if not items:
        raise ValueError("items.json holds no item for document " + doc["id"])
    unknown = sorted({str(i["benchmark"]).lower() for i in items} - set(spec["benchmarks"]))
    if unknown:
        raise ValueError("no prompt for benchmark " + ", ".join(unknown))
    reader = reader or resolve_reader()
    context = SimpleNamespace(run_dir=str(out), run_id=run_id or ("b1-" + uuid.uuid4().hex[:12]))
    backend = backend or LocalBackend(reader, context)
    conventions = conventions_block(data["registry"])
    decoding = dict(decoding_policy.usage_fields(reader["decoding"]),
                    max_new_tokens=reader["max_new_tokens"])
    summary = {}
    for item in items:
        bench_key = str(item["benchmark"]).lower()
        bench = spec["benchmarks"][bench_key]
        user = render_user(spec, bench_key, document=doc["text"], conventions=conventions, item=item)
        error, result = "", {}
        try:
            result = backend.generate(spec["system"], user, reader["max_new_tokens"]) or {}
        except Exception as exc:  # a failed call is an unparseable reply, and still a record
            error = type(exc).__name__
        reply = result.get("text") if isinstance(result.get("text"), str) else None
        call_id = reply_records.write(
            context, agent=AGENT_LABEL, backend=reader["backend"], model_id=reader["model_id"],
            model_mode=reader["model_mode"], payload=result.get("payload"),
            payload_form=result.get("form"), reply=reply, ok=not error, error=error,
            decoding=decoding, phase=ARM, doc_id=doc["id"])
        parsed = parse_reply(reply, bench, item["item_id"]) if not error else dict(
            parse_reply(None, bench), failure="backend_failure")
        undecided = bool(parsed["parsed"]) and _norm_label(parsed["label"]) == _norm_label(bench["undecided"])
        _write_json(out / "labels" / (str(item["item_id"]) + ".json"), {
            "baseline": BASELINE_TEXT, "arm": ARM, "schema": "b1-label-v1",
            "item_id": item["item_id"], "document_id": doc["id"], "rule_id": item["rule_id"],
            "benchmark": bench_key, "label": parsed["label"], "abstain": not parsed["parsed"],
            "undecided": undecided, "parse_failure": parsed["failure"],
            "evidence": parsed["evidence"], "reason": parsed["reason"],
            "reply_item_id": parsed["reply_item_id"], "item_id_matches": parsed["item_id_matches"],
            "call_id": call_id, "backend_ok": not error, "reading_agent": reader["agent"],
            "model_id": reader["model_id"], "model_mode": reader["model_mode"]})
        row = summary.setdefault(bench_key, {"items": 0, "parsed": 0, "undecided": 0,
                                             "abstain": 0, "backend_failures": 0})
        row["items"] += 1
        row["parsed"] += int(parsed["parsed"])
        row["undecided"] += int(undecided)
        row["abstain"] += int(not parsed["parsed"])
        row["backend_failures"] += int(bool(error))
    for row in summary.values():
        row["parse_rate"] = row["parsed"] / row["items"]
    result = {"baseline": BASELINE_TEXT, "arm": ARM, "finished_at": _now(), "run_id": context.run_id,
              "bundle": Path(bundle).name, "document_id": doc["id"],
              "prompt": {"source": spec.get("source"), "status": spec.get("status")},
              "reader": {k: reader[k] for k in ("agent", "backend", "model_id", "model_mode",
                                                "max_new_tokens", "max_new_tokens_source")},
              "decoding": decoding, "benchmarks": summary}
    _write_json(out / "b1_summary.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--items", required=True, help="items.json written beside the bundle")
    parser.add_argument("--out", required=True)
    parser.add_argument("--agent", default=READING_AGENT)
    parser.add_argument("--profile", choices=["local", "registry"], default="local")
    parser.add_argument("--max-new-tokens", type=int, default=None)
    args = parser.parse_args(argv)
    reader = resolve_reader(agent=args.agent, profile=args.profile,
                            max_new_tokens=args.max_new_tokens)
    result = run(args.bundle, args.items, args.out, reader=reader)
    print(json.dumps(result["benchmarks"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
