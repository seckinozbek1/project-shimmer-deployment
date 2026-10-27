"""B1, the bare-model arm: the main reading agent's model, one fixed prompt per item, no pipeline.

An evaluation tool, not a review. For one test bundle and the item table the adapter
wrote beside it (``items.json``: item_id, document_id, rule_id, benchmark; no gold;
the source ids it also holds are never put in a prompt), it sends the preregistered
prompt (``b1_prompt.json``, from docs/benchmarks/PREREGISTRATION.md section 5.4) once
per item. The prompt is rendered by benchmark/adapters/common/prompt.py, the same code
the adapters' cut rule counts with: the document as it stands in the bundle (already cut
by the adapter, section 5.3), every convention of the bundle as written in it, and the
bundle's reference material (its grounding files, the earlier version included), or the
line ``None.`` when it has none. It writes:

  <out>/audit/model_replies/   one record per call, through reply_records.write (the
                               S1 Part 4 write path every pipeline backend uses); the
                               run stops if a record cannot be written
  <out>/labels/<item_id>.json  one typed label per item; a reply that does not parse,
                               or whose label is not in the list, is ABSTAIN
  <out>/b1_summary.json        counts and the parse rate per benchmark, the number of
                               replies whose length reached the output allowance
                               (possibly truncated), and whether the parse rate is
                               below the development floor of 95 percent

Before the first item the model is loaded and verified ONCE: its model id, checkpoint
digest and decoding are compared with the values passed in (from VERSIONS.md; section 4),
and every item's prompt plus the output allowance must fit the model's context. Any
failure there stops the run with a non-zero exit before anything is generated. Inside
the item loop only a generation error is caught (and recorded as a failed call).

The reading agent is passed in (``--agent``). PROCESSOR is a PLACEHOLDER default until
preregistration section 12 item 8 names the main reading agent. Its backend comes from
the pipeline's local profile table and config/local_models.json (read as data, the
pipeline is never imported), its checkpoint through final_models in final mode, its
decoding policy through scripts/decoding_policy.py, and its output allowance from the
pipeline's PROCESSOR budget (PRODUCTION_MAX_TOKENS) unless --max-new-tokens overrides it.

Usage (loads a local model; for the rented machine, never this laptop):
    py -3.12 benchmark/baselines/bare_model.py --bundle <bundle> --items <items.json> --out <dir>
        --agent <AGENT> --expect-model-id <id> --expect-digest <sha256> --expect-decoding '<json>'
"""
from __future__ import annotations

import argparse

import hashlib
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
ADAPTERS = HERE.parent / "adapters"
for _p in (str(SCRIPTS), str(HERE), str(ADAPTERS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import decoding_policy  # noqa: E402
import final_models  # noqa: E402
import python_only  # noqa: E402  the bundle loader shared with B2
import reply_records  # noqa: E402
from common import prompt as b1_prompt  # noqa: E402  the one renderer of the section 5.4 prompt

ARM = "B1"
AGENT_LABEL = "B1_BARE_MODEL"
BASELINE_TEXT = "BASELINE B1 (bare model): one fixed prompt per item, no pipeline. This is not a review."
PROMPT_PATH = HERE / "b1_prompt.json"
READING_AGENT = "PROCESSOR"   # PLACEHOLDER until preregistration section 12 item 8 is settled
PIPELINE_SOURCE = SCRIPTS / "pipeline.py"
_FENCE = re.compile(r"^\s*```[^`\s]*\s*$")
_ESCAPE = re.compile(r'\\(["\\/bfnrtu])|\\')
UNCERTAIN_LABEL = "uncertain"
# Section 5.4 (D-039 item 11): a benchmark whose development parse rate is below this floor
# has its prompt and parser revised before the freeze.
PARSE_RATE_FLOOR = 0.95


class SetupError(Exception):
    """A failure before or outside generation: never caught per item."""


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# the prompt


def load_prompt(path=PROMPT_PATH):
    spec = b1_prompt.load_prompt(path)
    for name, bench in spec["benchmarks"].items():
        names = label_names(bench)
        if _norm_label(bench["undecided"]) not in {_norm_label(n) for n in names}:
            raise ValueError("the undecided label of %s is not one of its labels" % name)
    return spec


def label_names(bench):
    """The label names: each label line's text before its first colon."""
    return [line.split(":", 1)[0].strip() for line in bench["labels"]]


def render_user(spec, bench_key, *, document, conventions, item, reference=""):
    return b1_prompt.render_user(spec, bench_key, document=document, conventions=conventions,
                                 item=item, reference=reference)


def render_system(spec, bench_key):
    return b1_prompt.render_system(spec, bench_key)


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


def _loads(candidate):
    """(object, repaired): the JSON object, or, when it does not parse, the same text with
    every backslash that starts no valid JSON escape doubled (a copied `\\|`, `\\#` or
    LaTeX command in `evidence` or `reason` must not cost the label)."""
    try:
        return json.loads(candidate), False
    except ValueError:
        fixed = _ESCAPE.sub(lambda m: m.group(0) if m.group(1) else "\\\\", candidate)
        return json.loads(fixed), True


def parse_reply(reply, bench, item_id=None):
    """{parsed, label, evidence, reason, reply_item_id, item_id_matches, failure, repaired}."""
    out = {"parsed": False, "label": None, "evidence": None, "reason": None,
           "reply_item_id": None, "item_id_matches": None, "failure": None, "repaired": False}
    if not isinstance(reply, str) or not reply.strip():
        out["failure"] = "empty_reply"
        return out
    kept = "\n".join(line for line in reply.splitlines() if not _FENCE.match(line))
    candidate = _last_balanced_object(kept)
    if candidate is None:
        out["failure"] = "no_json_object"
        return out
    try:
        obj, out["repaired"] = _loads(candidate)
    except ValueError:
        out["failure"] = "json_invalid"
        return out
    if not isinstance(obj, dict) or not isinstance(obj.get("label"), str):
        out["failure"] = "no_label"
        return out
    wanted = _norm_label(obj["label"])
    if wanted == UNCERTAIN_LABEL:  # a rule's "emit UNCERTAIN" means the undecided label
        wanted = _norm_label(bench["undecided"])
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
# the model, read from the pipeline's own configuration


pipeline_literal = python_only.pipeline_literal  # one ast reader of the pipeline source


def resolve_reader(root=ROOT, *, agent=READING_AGENT, profile="local", max_new_tokens=None):
    """The reading agent's backend, model, decoding policy and output allowance."""
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
    return {"agent": agent, "agent_source": "placeholder" if agent == READING_AGENT else "argument",
            "backend": backend, "model_id": model_id, "model_mode": mode,
            "role": role, "decoding": decoding, "max_new_tokens": allowance,
            "max_new_tokens_source": "argument" if max_new_tokens is not None
            else "pipeline PRODUCTION_MAX_TOKENS", "sources": sources}


class LocalBackend:
    """The model, loaded and called the way agent_wrapper.call_local loads and calls it:
    final mode through final_models.resident, base mode through the shared loader, the
    model's own chat template with a system and a user turn, the frozen decoding kwargs.
    prepare() loads it once; nothing generates before that."""

    def __init__(self, reader, run_context):
        self.reader, self.run_context = reader, run_context
        self._tok = self._mdl = None

    def prepare(self):
        """Load and verify; returns {model_id, digest, decoding} of what was loaded."""
        if self.reader["model_mode"] == "final" and self.reader["backend"] == "local_producer":
            final_models.verify_runtime()
            self._tok, self._mdl = final_models.resident("producer", self.run_context)
            ident = final_models.identity("producer")
            digest = ident["adapter_sha256"]
        else:
            import agent_wrapper
            from huggingface_hub import snapshot_download
            self._tok, self._mdl = agent_wrapper._load_qwen(self.reader["model_id"])
            # PROVISIONAL: a base checkpoint is identified by its local snapshot revision
            snapshot = Path(snapshot_download(self.reader["model_id"], local_files_only=True))
            digest = "snapshot:" + snapshot.name
        return {"model_id": self.reader["model_id"], "digest": digest,
                "decoding": dict(self.reader["decoding"]["kwargs"])}

    def _loaded(self):
        if self._tok is None:
            raise SetupError("the model was not prepared before the first call")
        return self._tok, self._mdl

    def _render(self, system, user):
        tok, _ = self._loaded()
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    def count_prompt(self, system, user):
        tok, _ = self._loaded()
        return len(tok(self._render(system, user), add_special_tokens=False)["input_ids"])

    def count(self, text):
        tok, _ = self._loaded()
        return len(tok(text, add_special_tokens=False)["input_ids"])

    def max_context(self):
        _, mdl = self._loaded()
        return int(mdl.config.max_position_embeddings)

    def generate(self, system, user, max_new_tokens):
        import torch
        tok, mdl = self._loaded()
        prompt = self._render(system, user)
        inputs = tok(prompt, return_tensors="pt", add_special_tokens=False).to(mdl.device)
        with torch.no_grad():
            out = mdl.generate(**inputs, max_new_tokens=max_new_tokens,
                               **self.reader["decoding"]["kwargs"])
        start = int(inputs["input_ids"].shape[1])
        generated = int(out[0].shape[0]) - start
        text = tok.decode(out[0][start:], skip_special_tokens=True)
        del inputs, out
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return {"text": text, "payload": prompt, "form": "rendered_prompt",
                "output_tokens": generated}


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


def _hashed(text):
    if text is None:
        return None
    data = text.encode("utf-8")
    return {"sha256": hashlib.sha256(data).hexdigest(), "length_bytes": len(data)}


def verify_identity(loaded, expected):
    """Compare what was loaded with the values passed in (VERSIONS.md): a mismatch stops
    the run (section 4)."""
    wrong = [key for key in ("model_id", "digest", "decoding")
             if key in expected and expected[key] != loaded.get(key)]
    if wrong:
        raise SetupError("loaded model differs from the recorded values on: " + ", ".join(wrong))


def length_reached(result, allowance):
    """True when the reply's length reached the output allowance (it may be cut short),
    False when it did not, None when the backend does not report its output length."""
    tokens = result.get("output_tokens") if isinstance(result, dict) else None
    if type(tokens) is not int:
        return None
    return tokens >= int(allowance)


def run(bundle, items_path, out, *, backend=None, reader=None, prompt_path=PROMPT_PATH,
        run_id=None, expected=None, development=False, sensitive=False):
    """Run B1 on one bundle. `backend` needs prepare() -> {model_id, digest, decoding},
    count_prompt(system, user), max_context() and generate(system, user, max_new_tokens)
    -> {text, payload, form, output_tokens}; None builds the LocalBackend (a real model load).
    `expected` holds the recorded model_id, digest and decoding; it may be omitted only
    with development=True, which is recorded."""
    out = Path(out)
    if not expected and not development:
        raise SetupError("the recorded model id, checkpoint digest and decoding are required "
                         "(section 4); only a development run may omit them")
    spec = load_prompt(prompt_path)
    data = python_only.load_bundle(bundle)
    if len(data["targets"]) != 1:
        raise ValueError("a benchmark bundle names exactly one document under review")
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
    conventions = b1_prompt.conventions_from_bundle(bundle)
    reference = b1_prompt.reference_from_bundle(bundle)
    # Load and verify once, before the first item; nothing below is caught.
    loaded = backend.prepare()
    verify_identity(loaded, expected or {})
    users = {i["item_id"]: render_user(spec, str(i["benchmark"]).lower(), document=doc["text"],
                                       conventions=conventions, item=i, reference=reference)
             for i in items}
    systems = {i["item_id"]: render_system(spec, str(i["benchmark"]).lower()) for i in items}
    limit = backend.max_context()
    over = [i for i, user in users.items()
            if backend.count_prompt(systems[i], user) + reader["max_new_tokens"] > limit]
    if over:
        raise SetupError("prompt plus output allowance exceeds the model's context for %d item(s): %s"
                         % (len(over), ", ".join(over[:5])))
    decoding = dict(decoding_policy.usage_fields(reader["decoding"]),
                    max_new_tokens=reader["max_new_tokens"])
    summary, written = {}, []
    for item in items:
        bench_key = str(item["benchmark"]).lower()
        bench = spec["benchmarks"][bench_key]
        error, result = "", {}
        try:
            result = backend.generate(systems[item["item_id"]], users[item["item_id"]],
                                      reader["max_new_tokens"]) or {}
        except SetupError:
            raise
        except Exception as exc:  # a generation error is a failed call, and still a record
            error = type(exc).__name__
        reply = result.get("text") if isinstance(result.get("text"), str) else None
        call_id = reply_records.write(
            context, agent=AGENT_LABEL, backend=reader["backend"], model_id=reader["model_id"],
            model_mode=reader["model_mode"], payload=result.get("payload"),
            payload_form=result.get("form"), reply=reply, ok=not error, error=error,
            decoding=decoding, sensitive=sensitive, phase=ARM, doc_id=doc["id"])
        if not call_id:
            raise SetupError("the reply record for item %s could not be written" % item["item_id"])
        written.append(call_id)
        parsed = parse_reply(reply, bench, item["item_id"]) if not error else dict(
            parse_reply(None, bench), failure="backend_failure")
        undecided = bool(parsed["parsed"]) and _norm_label(parsed["label"]) == _norm_label(bench["undecided"])
        reached = None if error else length_reached(result, reader["max_new_tokens"])
        texts = ({"evidence": parsed["evidence"], "reason": parsed["reason"]} if not sensitive else
                 {"evidence": None, "reason": None, "evidence_hashed": _hashed(parsed["evidence"]),
                  "reason_hashed": _hashed(parsed["reason"])})
        _write_json(out / "labels" / (str(item["item_id"]) + ".json"), dict({
            "baseline": BASELINE_TEXT, "arm": ARM, "schema": "b1-label-v2",
            "item_id": item["item_id"], "document_id": doc["id"], "rule_id": item["rule_id"],
            "benchmark": bench_key, "label": parsed["label"], "abstain": not parsed["parsed"],
            "undecided": undecided, "parse_failure": parsed["failure"],
            "parse_repaired": parsed["repaired"], "output_tokens": result.get("output_tokens")
            if type(result.get("output_tokens")) is int else None,
            "length_reached_allowance": reached}, **texts, **{
            "reply_item_id": parsed["reply_item_id"], "item_id_matches": parsed["item_id_matches"],
            "call_id": call_id, "backend_ok": not error, "reading_agent": reader["agent"],
            "model_id": reader["model_id"], "model_mode": reader["model_mode"]}))
        row = summary.setdefault(bench_key, {"items": 0, "parsed": 0, "undecided": 0,
                                             "abstain": 0, "backend_failures": 0, "repaired": 0,
                                             "length_reached_allowance": 0,
                                             "length_not_reported": 0})
        row["items"] += 1
        row["length_reached_allowance"] += int(reached is True)
        row["length_not_reported"] += int(reached is None)
        row["parsed"] += int(parsed["parsed"])
        row["undecided"] += int(undecided)
        row["abstain"] += int(not parsed["parsed"])
        row["backend_failures"] += int(bool(error))
        row["repaired"] += int(parsed["repaired"])
    if len(written) != len(items) or len(set(written)) != len(items):
        raise SetupError("reply records (%d) do not match items (%d)" % (len(set(written)), len(items)))
    for row in summary.values():
        row["parse_rate"] = row["parsed"] / row["items"]
        row["parse_rate_floor"] = PARSE_RATE_FLOOR
        row["below_parse_rate_floor"] = row["parse_rate"] < PARSE_RATE_FLOOR
    result = {"baseline": BASELINE_TEXT, "arm": ARM, "finished_at": _now(), "run_id": context.run_id,
              "bundle": Path(bundle).name, "document_id": doc["id"],
              "prompt": {"source": spec.get("source"), "status": spec.get("status")},
              "reader": {k: reader[k] for k in ("agent", "agent_source", "backend", "model_id",
                                                "model_mode", "max_new_tokens", "max_new_tokens_source")},
              "loaded": loaded, "verified_against": sorted((expected or {}).keys()),
              "development": bool(development), "sensitive": bool(sensitive),
              "reference_material": bool(reference), "decoding": decoding, "benchmarks": summary}
    _write_json(out / "b1_summary.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--items", required=True, help="items.json written beside the bundle")
    parser.add_argument("--out", required=True)
    parser.add_argument("--agent", default=READING_AGENT,
                        help="the main reading agent (PROCESSOR is a placeholder pending section 12 item 8)")
    parser.add_argument("--profile", choices=["local", "registry"], default="local")
    parser.add_argument("--max-new-tokens", type=int, default=None)
    parser.add_argument("--expect-model-id")
    parser.add_argument("--expect-digest")
    parser.add_argument("--expect-decoding", help="the decoding kwargs as a JSON object")
    parser.add_argument("--development", action="store_true",
                        help="development run: the recorded values may be omitted (recorded)")
    parser.add_argument("--sensitive", action="store_true",
                        help="keep only hashes of prompts, replies, evidence and reason")
    args = parser.parse_args(argv)
    expected = {}
    if args.expect_model_id:
        expected["model_id"] = args.expect_model_id
    if args.expect_digest:
        expected["digest"] = args.expect_digest
    if args.expect_decoding:
        expected["decoding"] = json.loads(args.expect_decoding)
    try:
        reader = resolve_reader(agent=args.agent, profile=args.profile,
                                max_new_tokens=args.max_new_tokens)
        result = run(args.bundle, args.items, args.out, reader=reader, expected=expected,
                     development=args.development, sensitive=args.sensitive)
    except Exception as exc:  # setup, load, verification or record failure: stop, non-zero
        print("B1 stopped before or during the run: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 4
    print(json.dumps(result["benchmarks"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
