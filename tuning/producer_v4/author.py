"""Producer v4 rows: v3's compositional method on real public carrier text (docs/loop/PRODUCER_TRAINING_PLAN.md).

    py -3.12 -X utf8 tuning/producer_v4/author.py --carriers external/s05/P1/carriers_raw \
        --test-prompts <replay file> [--test-prompts <another> ...] --out external/s05/P1/v4

Local only: v3's guard (tuning/producer_v3/local_common.py) is installed first, so no network, no
subprocess, no model weight and no benchmark data is read; the tokenizer is read from the local
cache only, to render the fresh set's prompts exactly as the DEV prompts were rendered (proved here
on every DEV row against the protocol's prompt digests).

A carrier is three consecutive sentences of a public document (sources.json) that the frozen
policy's own interpreter reads as stating NOTHING (no gap, no uncertainty, no refusal): real prose
with no planted meaning. Python inserts v3's declared clauses (the same GAPS and UNCERTAINTY lists,
claims under CLM ids citing REF ids) between its sentences, and the frozen interpreter labels the
whole span, so every label is the policy's reading and none is judged. A carrier the interpreter
refuses is a whole-packet refusal row, the policy's own behaviour for content outside its finite
ontology. A carrier sharing an 8-word run with any test prompt is dropped. Rows are written in
168's training form (the two turns of tuning/first_domain_agnostic_v1/common.py messages, the
answer the canonical target); the fresh set as a replay file of the rendered prompts, each asked of
`tuned` and `candidate`, its reference the SHA-256 of the canonical target.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tuning" / "producer_v3"))
from local_common import canonical, v2  # noqa: E402  (installs v3's local-only guard)
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("producer_v3_author", ROOT / "tuning" / "producer_v3" / "author.py")
v3 = importlib.util.module_from_spec(_spec)  # v3's GAPS, UNCERTAINTY and label, under its own name; run() is never called
_spec.loader.exec_module(v3)
sys.path.insert(0, str(ROOT / "tuning" / "first_domain_agnostic_v1"))
import common as old  # noqa: E402

SEED = "producer-v4:20261108:"
WINDOW = 3
MIN_CHARS, MAX_CHARS = 250, 900
RUN_WORDS = 8
DASHES = {"\u2014": ", ", "\u2013": "-", "\u2012": "-", "\u2015": ", "}
FORBIDDEN = ("CLM-", "REF-", "CONTEXT ONLY")
CONTEXT = "CONTEXT ONLY: CLM-OUTSIDE identifies a separate collection (REF-990001)."


def _h(text):
    return hashlib.sha256((SEED + text).encode("utf-8")).hexdigest()


def clean(text):
    for k, v in DASHES.items():
        text = text.replace(k, v)
    text = "".join(c if c.isprintable() or c == " " else " " for c in text)
    return re.sub(r"\s+", " ", text).strip()


def windows(doc):
    """Consecutive three-sentence windows of a document's sentences in order, cleaned (a source
    that publishes one sentence a paragraph, as FinQA does, is read as one run of sentences)."""
    out, sentences = [], []
    for paragraph in doc["paragraphs"]:
        sentences += [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", clean(paragraph)) if s]
    for i in range(0, max(0, len(sentences) - WINDOW + 1), WINDOW):
        text = " ".join(sentences[i:i + WINDOW])
        if MIN_CHARS <= len(text) <= MAX_CHARS and not any(f in text for f in FORBIDDEN):
            out.append(sentences[i:i + WINDOW])
    return out


def reading(text):
    """'none', 'atoms' or 'refused': the frozen interpreter on a carrier alone."""
    atoms = []
    try:
        for clause in v3.semantic_segments(text):
            atoms += v2.sem.interpretations(clause, text, "s0", [])
    except ValueError:
        return "refused"
    return "atoms" if atoms else "none"


def word_runs(text):
    words = re.findall(r"\w+", text.lower())
    return {" ".join(words[i:i + RUN_WORDS]) for i in range(len(words) - RUN_WORDS + 1)}


def test_runs(paths):
    runs = set()
    for path in paths:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        for p in value.get("prompts") or []:
            runs |= word_runs(p["prompt"])
    return runs


def plan(n, sentences, letters=0):
    """The clauses of row n, from v3's lists, placed between the carrier's sentences: one or two
    gaps, maybe an uncertainty, zero to three claims, by the row number alone (v3's arithmetic)."""
    primary, secondary, u = n % 20, (7 + 3 * n) % 20, n % 8
    clauses = [v3.GAPS[primary]] + ([v3.GAPS[secondary]] if n % 3 else []) + ([] if n % 5 == 0 else [v3.UNCERTAINTY[u]])
    claims = n % 4
    prefix = ["CLM-K%s: The record logged %d units (REF-%d)." % (chr(65 + letters + k), 31 + n % 50 + 5 * k, 70000 + 4 * n + k) for k in range(claims)]
    body = list(sentences)
    for k, clause in enumerate(prefix + clauses):
        body.insert(min(len(body), 1 + (k * 2 + n) % (len(body) + 1)), clause)
    return body


def packet(texts):
    spans = [dict(alias="s%x" % (k * 4096), text=t) for k, t in enumerate(texts)]
    refs = sorted(set(re.findall(r"REF-\d{4,}", " ".join(s["text"] for s in spans))))
    return dict(role="producer", production_contract="semantic-task-v1", source_spans=spans,
                context_only_spans=[dict(alias="sffff", text=CONTEXT)], supplied_refs=refs + ["REF-990001"],
                required_refs=refs, routed_rules=[])


def row_of(n, name, doc_id, sentences, refused=False, second=None):
    """One row, or None when the frozen interpreter will not label it."""
    texts = ["Section %d\n%s" % (n, " ".join(sentences if refused else plan(n, sentences)))]
    if second is not None:
        texts.append("Section %d continued\n%s" % (n, " ".join(plan(n + 1, second, letters=3))))
    p = packet(texts)
    try:
        label = v3.label(p, refuse=refused)
        if not refused:
            v2.sem.validate_label(label, p)
        target = v2.sem.render(label)
    except (ValueError, AssertionError):
        return None
    row = {"role": "producer", "input": p}
    messages = old.messages(row)
    return {"row_id": "v4-%s-%04d" % (name, n), "family": name, "doc_id": doc_id, "share_alike": False,
            "system": messages[0]["content"], "user": messages[1]["content"],
            "answer": canonical(target).decode() if isinstance(canonical(target), bytes) else canonical(target),
            "refusal": refused, "spans": len(texts)}


def build(carriers, sources, runs, use, quota, start):
    """quota rows for one source and use, about one in ten a refusal, about three in ten two spans."""
    docs = [json.loads(l) for l in Path(carriers).read_text(encoding="utf-8").splitlines() if l.strip()]
    plain, refusing, dropped = [], [], 0
    for doc in docs:
        for sentences in windows(doc):
            text = " ".join(sentences)
            if word_runs(text) & runs:
                dropped += 1
                continue
            kind = reading(text)
            if kind == "none":
                plain.append((doc["doc_id"], sentences))
            elif kind == "refused":
                refusing.append((doc["doc_id"], sentences))
    plain.sort(key=lambda d: _h(use + d[0] + " ".join(d[1])))
    refusing.sort(key=lambda d: _h(use + d[0] + " ".join(d[1])))
    rows, n, used_docs = [], start, set()
    want_refusals = max(1, quota // 10)
    for doc_id, sentences in refusing:
        if sum(r["refusal"] for r in rows) >= want_refusals:
            break
        row = row_of(n, sources, doc_id, sentences, refused=True)
        n += 1
        if row:
            rows.append(row)
            used_docs.add(doc_id)
    i = 0
    while len(rows) < quota and i < len(plain):
        doc_id, sentences = plain[i]
        two = (n % 10) < 3 and i + 1 < len(plain)
        row = row_of(n, sources, doc_id, sentences, second=plain[i + 1][1] if two else None)
        i += 2 if two else 1
        n += 2 if two else 1
        if row:
            rows.append(row)
            used_docs.add(doc_id)
    return rows, {"windows_plain": len(plain), "windows_refused": len(refusing), "dropped_overlap": dropped,
                  "rows": len(rows), "refusals": sum(r["refusal"] for r in rows), "two_spans": sum(r["spans"] == 2 for r in rows),
                  "documents_used": sorted(used_docs)}, n


def tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(old.cached("producer")), local_files_only=True, trust_remote_code=False)


def render(tok, system, user):
    return tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                   tokenize=False, add_generation_prompt=True)


def prove_rendering(tok):
    """Every DEV row rendered here equals the protocol's prepared prompt digest (EXTRACTION-A)."""
    protocol = json.loads((ROOT / "tuning/producer_v3/evaluation_protocol.json").read_bytes().replace(b"\r\n", b"\n").decode("utf-8"))
    dataset = {r["example_id"]: r for r in json.loads((ROOT / "tuning/producer_v3/dataset.json").read_text(encoding="utf-8"))}
    for example_id in protocol["dev_ids"]:
        messages = old.messages(dataset[example_id])
        text = render(tok, messages[0]["content"], messages[1]["content"])
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != protocol["prompt_bindings"][example_id]["prompt_sha256"]:
            raise ValueError("this renderer does not reproduce DEV row " + example_id)
    return len(protocol["dev_ids"])


def validate_targets(tok, rows):
    """Every row's answer through the run's own compact validator, unchanged, on its rendered
    prompt (contract_decoding.validate_rendered): a non-refusal row whose target the validator
    refuses is a row the test could never score right, so the build stops. A refusal row's target
    is the refusal object, which the validator refuses by design (DEV's nine refusals)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import contract_decoding
    counts = {"valid": 0, "refusal_refused_as_designed": 0}
    for row in rows:
        reason = contract_decoding.validate_rendered(render(tok, row["system"], row["user"]), row["answer"])
        if reason is None and not row["refusal"]:
            counts["valid"] += 1
        elif reason is not None and row["refusal"]:
            counts["refusal_refused_as_designed"] += 1
        else:
            raise ValueError("the validator disagrees with the target of %s: %s" % (row["row_id"], reason))
    return counts


def fresh_file(tok, rows, cap):
    prompts = []
    for row in rows:
        text = render(tok, row["system"], row["user"])
        for checkpoint in ("tuned", "candidate"):
            prompts.append({"prompt_id": "p%04d" % (len(prompts) + 1), "set": "fresh", "source_call_id": row["row_id"],
                            "source_run_id": "producer-v4-fresh", "agent": "PROCESSOR_FRESH", "backend": "local_producer",
                            "checkpoint": checkpoint, "pair_of": row["row_id"], "doc_id": row["doc_id"], "max_new_tokens": cap,
                            "prompt_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            "reference_reply_sha256": hashlib.sha256(row["answer"].encode("utf-8")).hexdigest(), "prompt": text})
    return {"schema": "b3-replay-prompts-v1", "sources": [{"fresh_rows": len(rows)}], "min_chars": 0,
            "prompt_count": len(prompts), "prompts": prompts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--carriers", required=True)
    parser.add_argument("--test-prompts", action="append", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    declared = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    runs = test_runs(args.test_prompts)
    train, fresh, report, n = [], [], {}, 0
    for name, source in declared["sources"].items():
        if source["use"] != "train":
            continue
        rows, info, n = build(Path(args.carriers) / ("%s_train.jsonl" % name), name, runs, "train", source["rows"], n)
        train += rows
        report[name + ":train"] = info
    v3_rows = json.loads((ROOT / "tuning/producer_v3/dataset.json").read_text(encoding="utf-8"))
    split = json.loads((ROOT / "tuning/producer_v3/split.json").read_text(encoding="utf-8"))
    keep = set(split["train"])
    for r in v3_rows:
        if r["example_id"] in keep:
            messages = old.messages(r)
            target = v2.target(r)
            train.append({"row_id": r["example_id"], "family": "v3:" + r["domain"], "doc_id": r["example_id"], "share_alike": False,
                          "system": messages[0]["content"], "user": messages[1]["content"],
                          "answer": canonical(target).decode() if isinstance(canonical(target), bytes) else canonical(target),
                          "refusal": bool(r.get("refusal_basis")), "spans": len(r["input"]["source_spans"])})
    for name, count in (("gov_report", 17), ("billsum", 17), ("qasper", 16)):
        rows, info, n = build(Path(args.carriers) / ("%s_fresh.jsonl" % name), name, runs, "fresh", count, n)
        fresh += rows
        report[name + ":fresh"] = info
    rows, info, n = build(Path(args.carriers) / "pubmed_qa_fresh.jsonl", "pubmed_qa", runs, "fresh", 50, n)
    fresh += rows
    report["pubmed_qa:fresh"] = info
    train_docs = {(r["family"], r["doc_id"]) for r in train}
    if any((r["family"], r["doc_id"]) in train_docs for r in fresh):
        raise ValueError("a fresh row comes from a training document")
    if {r["user"] for r in train} & {r["user"] for r in fresh}:
        raise ValueError("a payload sits in training and in the fresh set")
    tok = tokenizer()
    proved = prove_rendering(tok)
    validated = {"fresh": validate_targets(tok, fresh), "train_v4": validate_targets(tok, [r for r in train if not r["family"].startswith("v3:")])}
    protocol = json.loads((ROOT / "tuning/producer_v3/evaluation_protocol.json").read_bytes().replace(b"\r\n", b"\n").decode("utf-8"))
    fields = ("row_id", "system", "user", "answer", "family", "share_alike")
    (out / "train_rows.json").write_text(json.dumps([{k: r[k] for k in fields} for r in train], ensure_ascii=False, indent=0) + "\n",
                                         encoding="utf-8", newline="\n")
    (out / "fresh_prompts.json").write_text(json.dumps(fresh_file(tok, fresh, protocol["generation_kwargs"]["max_new_tokens"]),
                                                       ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    families = {}
    for r in train:
        key = r["family"].split(":")[0]
        families[key] = families.get(key, 0) + 1
    bench = {k for k, s in declared["sources"].items() if s.get("benchmark_family")}
    manifest = {"schema": "producer-v4-data-manifest-v1", "sources": declared["sources"], "excluded": declared["excluded"],
                "train_rows": len(train), "by_family": families,
                "benchmark_family_rows": sum(v for k, v in families.items() if k in bench),
                "benchmark_family_share": round(sum(v for k, v in families.items() if k in bench) / len(train), 4),
                "fresh_rows": len(fresh), "fresh_by_source": {k: v["rows"] for k, v in report.items() if k.endswith(":fresh")},
                "refusals_train": sum(r["refusal"] for r in train), "two_span_rows_train": sum(r["spans"] == 2 for r in train),
                "build": report, "dev_rows_rendered_and_proved": proved, "targets_through_the_validator": validated, "test_prompt_files": [str(p) for p in args.test_prompts],
                "overlap_rule": "a carrier sharing an %d-word run with any test prompt is dropped" % RUN_WORDS,
                "train_rows_sha256": hashlib.sha256((out / "train_rows.json").read_bytes()).hexdigest(),
                "fresh_prompts_sha256": hashlib.sha256((out / "fresh_prompts.json").read_bytes()).hexdigest()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: manifest[k] for k in ("train_rows", "by_family", "benchmark_family_share", "fresh_rows", "fresh_by_source",
                                               "refusals_train", "two_span_rows_train", "train_rows_sha256", "fresh_prompts_sha256")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
