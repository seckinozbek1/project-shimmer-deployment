#!/usr/bin/env python3
"""Role V's labeller runner for the synthetic negotiation items (D-706 item 1, D-707; NEG_SYNTH_PIPELINE.md step 4).

It reads role S's label sheets ONLY (`tools/neg_synth.py label-sheets`: the round-k articles, the parties, the
persona, and each statement with its party and round), asks the declared labeller one narrow question per
statement (which article, which bracketed wording or the whole article, which stance, and for the persona's own
statements whether it is stated as a firm limit), and writes the labels `neg_synth.py label-compare` reads:
{item id: {POS id: {article, proposal, stance, red_line}}}. A sheet that carries a stance, a target, a red-line mark
or round k+1 is refused unread, so the labeller can never copy an answer.

The model is declared in config/neg_synth.json `labeller`, never in code: a family Shimmer does not use (OLMo,
with its written reason), an ordered list of candidate repositories read live on the instance (the first that
exists, is not gated and states the declared terms; its exact revision recorded), greedy decoding. A family of
the system under test or of the generator, or a dated snapshot id, is refused. Every reply is read once by the
project's one form reader (tools/answer_form.py, ANSWER-FORM-A); a field still not read leaves the position
unlabelled, counted by its reason, and label-compare then drops its item.

    run --sheets <V>/sheets_dev_1.json --out <V>/labels_dev_1.json --record <V>/LABELLER_dev_1.json

`run` loads the resolved model with transformers on the instance's GPU; the proofs inject a fake generate and
a fake resolver, so nothing is downloaded. It prints counts only, never a text or a label.

On Lambda (Seckin 18 November 2026 14:20: role V launches its own job under the guard, the ledger and the
reaper) the same questions ride the sealed replay pass (benchmark/baselines/neg_synth_label_pass.py):

    build-pass --sheets <V>/sheets_pilot_1.json --sheets <V>/sheets_dev_1.json
               --expect pilot_1=<sha256> --expect dev_1=<sha256> --out <work>/label_pass_prompts.json
    read-pass  --prompts <work>/label_pass_prompts.json --sheets <V>/sheets_dev_1.json
               --evidence <fetched collected_evidence.tar.gz or folder>
               --out <work>/labels_dev_1.json --record <work>/LABELLER_dev_1.json

`build-pass` checks each sheets file's SHA-256 against the one role S handed over and renders every question on
the laptop; `read-pass` reads each saved reply of one set once, from the fetched evidence, into the same labels
and record `run` writes. Both print counts and digests only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import neg_synth as ns  # noqa: E402
import answer_form as af  # noqa: E402
import neg_synth_label_pass as lp  # noqa: E402  (benchmark/baselines, on the path through neg_synth)

TEMPLATE_SCHEMA = "neg-synth-labeller-v1"
LABELS_SCHEMA = "neg-synth-labels-v1"
RECORD_SCHEMA = "neg-synth-labeller-record-v1"
CONFIDENCE_SCHEMA = "neg-synth-label-confidence-v1"
# Fields a label sheet must never carry: what would let the labeller copy its answer.
RENDER_SLOTS = ("round", "parties", "articles", "party", "statement_round", "quote", "article_ids",
                "firm_field", "example", "stance_definition")
ANSWER_FIELDS = ("stance", "article", "proposal", "red_lines", "red_line", "next_articles", "fate", "hidden",
                 "declared_key")


def load_template(cfg):
    t = json.loads((ROOT / cfg["labeller"]["template"]).read_text(encoding="utf-8"))
    if t.get("schema") != TEMPLATE_SCHEMA:
        raise ValueError("the labeller template's schema is not %s" % TEMPLATE_SCHEMA)
    return assert_no_shots(t)


def assert_no_shots(t):
    """D-736: no few-shot reuse of anyone's labels in the labeller's prompt. The template's one example is a form
    of placeholders (each value `<...>`), its text names no slot but the sheet's own, and render() reads the sheet,
    the position and this template alone, so no label, his or the labeller's, can reach a question."""
    example = t.get("example")
    if not isinstance(example, dict) or not all(isinstance(v, str) and v.startswith("<") and v.endswith(">")
                                                for v in example.values()):
        raise ValueError("refused: the labeller template's example carries a value, not a placeholder form")
    slots = set(re.findall(r"\{([a-z_]+)\}", t["template"]))
    if slots - set(RENDER_SLOTS):
        raise ValueError("refused: the labeller template names a slot render() does not fill from the sheet")
    return t


def check_model(model_id, cfg):
    """The labeller's model: a family the system under test and the generator never use, a bare id (the one rule,
    neg_synth_label_pass.check_model, which the instance applies too)."""
    return lp.check_model(model_id, cfg["labeller"], cfg["generation"]["generator_family"])


def resolve(cfg, info):
    """The first declared candidate that exists, is not gated and states the declared terms, read live through
    `info(repo) -> {exists, gated, terms, revision}` (huggingface_hub on the instance, a fake in the proofs)."""
    lab = cfg["labeller"]
    for repo in lab["candidates"]:
        meta = info(repo) or {}
        if meta.get("exists") and not meta.get("gated") and str(meta.get("terms", "")).lower() == lab["terms_required"]:
            return {"model_id": check_model(repo, cfg), "revision": meta.get("revision")}
    raise ValueError("refused: no declared labeller candidate resolves (exists, not gated, %s)" % lab["terms_required"])


def hub_info(repo):
    """Live metadata of a model repository (on the instance only)."""
    from huggingface_hub import model_info
    try:
        m = model_info(repo)
    except Exception:
        return {"exists": False}
    terms = getattr(getattr(m, "card_data", None), "license", None)
    return {"exists": True, "gated": bool(getattr(m, "gated", False)), "terms": terms or "", "revision": m.sha}


def check_sheets(value):
    """A label sheets file, refused when any sheet or position carries an answer field."""
    if not isinstance(value, dict) or value.get("schema") != ns.SHEET_SCHEMA:
        raise ValueError("refused: not a label sheets file")
    for sheet in value["sheets"]:
        if sheet.get("schema") != ns.SHEET_SCHEMA or any(f in sheet for f in ANSWER_FIELDS):
            raise ValueError("refused: a sheet carries an answer field")
        for p in sheet["positions"]:
            if set(p) - set(ns.SHEET_POSITION_FIELDS):
                raise ValueError("refused: a sheet's position carries more than its party, round and quote")
    return value["sheets"]


def render(sheet, position, t):
    persona = sheet["persona"]["id"]
    arts = "\n\n".join(t["article_line"].format(id=a["id"], title=a["title"],
                                                agreed=t["agreed_mark"] if a["agreed"] else "", text=a["text"])
                       for a in sheet["articles"])
    fills = {"round": str(sheet["round"]), "parties": ", ".join("%s (%s)" % (p["id"], p["kind"]) for p in sheet["parties"]),
             "articles": arts, "party": position["party"], "statement_round": str(position["round"]),
             "quote": position["quote"], "article_ids": ", ".join(a["id"] for a in sheet["articles"]),
             "firm_field": t["firm_field_persona"] if position["party"] == persona else t["firm_field_other"],
             "example": json.dumps(t["example"], ensure_ascii=False),
             # D-748: the stance definitions as config declares them (read with the template at call time).
             "stance_definition": t["stance_definition"]}
    out = t["template"]
    for name, value in fills.items():
        out = out.replace("{" + name + "}", value)
    return out


def _spans(article):
    return [s for s in ns.sna.bracket_spans(article["text"]) if s.strip()]


def _wordings(article):
    return len(_spans(article))


# The wording field's own refusals beyond answer_form's (lane/label-wording-reader, 19 November 2026): form only.
QUOTE_AMBIGUOUS = "quote_ambiguous"            # the value is the identical text of two or more bracketed wordings
QUOTE_NOT_EXACT = "quote_not_exact"            # the value only overlaps a bracketed wording: never guessed
NUMBER_ABOVE_ARTICLE = "number_above_article"  # a number above the chosen article's own count of wordings
WORDING_REASONS = (QUOTE_AMBIGUOUS, QUOTE_NOT_EXACT, NUMBER_ABOVE_ARTICLE)
# A matched pair of marks around a whole number ("[2]", "(2)", "<2>"), taken off as form.
MARKED_NUMBER = re.compile(r"^(?:\[\s*([0-9]+)\s*\]|\(\s*([0-9]+)\s*\)|<\s*([0-9]+)\s*>)$")


def marked_number(k):
    """The digits of a key that is a whole number, bare or in one matched pair of marks; else None."""
    found = MARKED_NUMBER.match(k)
    if found:
        return next(g for g in found.groups() if g)
    return k if k.isascii() and k.isdigit() else None


def quoted_wordings(k, span_keys):
    """The numbers (1-based, as text) of the bracketed wordings whose key IS `k`, the value written with or
    without one pair of the article's own brackets around it. Identity of keys only, never a part of one."""
    inner = af.key(k[1:-1]) if len(k) >= 2 and k[0] == "[" and k[-1] == "]" else None
    return [str(i + 1) for i, s in enumerate(span_keys) if s and (s == k or s == inner)]


def overlaps(k, span_keys):
    """True when `k` and a bracketed wording's key hold one another without being equal: refused, never read."""
    return bool(k) and any(s and s != k and (k in s or s in k) for s in span_keys)


def read_wording(value, article, t):
    """(the declared wording, None) or (None, reason): `whole` or the 1-based number of one of the chosen
    article's bracketed wordings, read by form only (WORDS-A, ANSWER-FORM-A), against the chosen article's own
    count n. In order: answer_form's own match against `whole` and 1..n; a whole number, bare or in one matched
    pair of marks, read as that number, and refused `number_above_article` above n; a value whose answer_form key
    IS the key of exactly one bracketed wording (with or without one pair of the article's own brackets around
    it) read as that wording's number, several refused `quote_ambiguous`, a value that only overlaps one refused
    `quote_not_exact`; a number reading and a quote reading that disagree refused `quote_ambiguous`. Nothing else
    is read: never a prefix, never a fuzzy or partial match."""
    spans, count = _spans(article), _wordings(article)
    declared = [t["whole"]] + [str(i) for i in range(1, count + 1)]
    got, why = af.match(value, declared)
    if why and why != af.NOT_DECLARED:
        return None, why
    text, _ = af.one_value(value)
    k = af.key(text)
    span_keys = [af.key(s) for s in spans]
    quoted = quoted_wordings(k, span_keys)
    if got is not None:
        return (got, None) if not quoted or quoted == [got] else (None, QUOTE_AMBIGUOUS)
    digits = marked_number(k)
    if digits is not None:
        n = int(digits)
        number = str(n) if 1 <= n <= count else None
        if quoted:
            return (number, None) if quoted == [number] else (None, QUOTE_AMBIGUOUS)
        if n > count:
            return None, NUMBER_ABOVE_ARTICLE
        return (number, None) if number else (None, af.NOT_DECLARED)
    if len(quoted) > 1:
        return None, QUOTE_AMBIGUOUS
    if quoted:
        return quoted[0], None
    if overlaps(k, span_keys):
        return None, QUOTE_NOT_EXACT
    return None, af.NOT_DECLARED


def read_answer(reply, sheet, position, t):
    """(label, None) or (None, reason): the reply read once by answer_form, every value against the sheet's own
    ids and the declared values; the wording through read_wording against the chosen article's own wordings."""
    obj, why, _several = af.last_object(reply)
    if why:
        return None, why
    arts = {a["id"]: a for a in sheet["articles"]}
    article, why = af.match(obj.get("article"), sorted(arts))
    if why:
        return None, "article:" + why
    wording, why = read_wording(obj.get("wording"), arts[article], t)
    if why:
        return None, "wording:" + why
    stance, why = af.match(obj.get("stance"), t["stances"])
    if why:
        return None, "stance:" + why
    firm = False
    if position["party"] == sheet["persona"]["id"]:
        value, why = af.match(obj.get("firm_limit"), sorted(t["firm_values"]))
        if why:
            return None, "firm_limit:" + why
        firm = t["firm_values"][value]
    return {"article": article, "proposal": None if wording == t["whole"] else int(wording), "stance": stance,
            "red_line": firm}, None


def label(sheets, generate, cfg, t):
    """({item: {POS: label}}, Counter of reasons): one prompt per position through `generate(prompts) -> replies`."""
    jobs = [(s, p) for s in sheets for p in s["positions"]]
    replies = generate([render(s, p, t) for s, p in jobs])
    if len(replies) != len(jobs):
        raise ValueError("the generator returned %d replies for %d prompts" % (len(replies), len(jobs)))
    return read_replies(jobs, replies, t)


def read_replies(jobs, replies, t):
    """Each (sheet, position)'s reply read once by answer_form into its label, or counted by its reason."""
    labels, reasons = {}, Counter()
    for (s, p), reply in zip(jobs, replies):
        lab, why = read_answer(reply, s, p, t)
        labels.setdefault(s["item_id"], {})
        if why:
            reasons[why] += 1
        else:
            labels[s["item_id"]][p["id"]] = lab
            reasons["read"] += 1
    return labels, reasons


def hf_generate(model_id, revision, decoding):
    """Greedy generation with the resolved model (on the instance's GPU only; never in a proof)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_id, revision=revision)
    model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision, torch_dtype=torch.bfloat16,
                                                 device_map="cuda")

    def generate(prompts):
        out = []
        for prompt in prompts:
            ids = tok.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True,
                                          return_tensors="pt").to(model.device)
            with torch.no_grad():
                gen = model.generate(ids, do_sample=bool(decoding["do_sample"]),
                                     max_new_tokens=int(decoding["max_new_tokens"]))
            out.append(tok.decode(gen[0, ids.shape[1]:], skip_special_tokens=True))
        return out
    return generate


def run(sheets_value, cfg, *, generate=None, info=None):
    """(labels file, labeller record): resolve the model live, label every position, count by reason."""
    t = load_template(cfg)
    sheets = check_sheets(sheets_value)
    model = resolve(cfg, info or hub_info)
    gen = generate or hf_generate(model["model_id"], model["revision"], cfg["labeller"]["decoding"])
    labels, reasons = label(sheets, gen, cfg, t)
    record = {"schema": RECORD_SCHEMA, "family": cfg["labeller"]["family"], "model_id": model["model_id"],
              "revision": model["revision"], "decoding": cfg["labeller"]["decoding"],
              "template_sha256": hashlib.sha256((ROOT / cfg["labeller"]["template"]).read_bytes()
                                                .replace(b"\r\n", b"\n")).hexdigest(),
              "sheets_sha256": ns._sha(sheets_value), "items": len(sheets),
              "positions": sum(len(s["positions"]) for s in sheets), "by_reason": dict(reasons),
              "labelled_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    return {"schema": LABELS_SCHEMA, "labels": labels}, record


def _file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def set_of(path):
    """A sheets file's set, from its name `sheets_<set>.json` (the form role S writes)."""
    name = Path(path).name
    if not (name.startswith("sheets_") and name.endswith(".json")) or not lp.SET_NAME.match(name[7:-5]):
        raise ValueError("refused: a sheets file is named sheets_<set>.json")
    return name[7:-5]


def declared_answers(sheet, position, t):
    """Each reply field's declared answer set for one question (what read_answer accepts, as surfaces): the
    sheet's article ids, `whole` and every wording number an article of the sheet holds, the stances, and the
    firm-limit values for the persona's own statements. The option sets only, never an answer.

    Recorded, not changed (lane/label-wording-reader): the wording set here is the sheet-wide 1..most, while
    read_wording reads against the chosen article's own 1..n. The set is fixed when the prompts file is built,
    before the model names its article, and the pass module (benchmark/baselines/neg_synth_label_pass.py, a bound
    file) takes one flat list per field; a per-article set needs that module to choose the list after the article
    field is decoded, so a re-seal and a new paid pass. Changing it here alone would also change every prompts
    file's digest, so the saved pass could no longer be read again. The confidence record's wording decision
    therefore runs over the sheet-wide values; the label never does.

    D-799 (lane/label-constrained): this set stays as it was, so a v1 file is read again unchanged; a v2 prompt
    also carries constraint_of's block, from which the pass chooses the wording list after the article is
    decoded, both for the constraint and for the confidence record."""
    most = max([_wordings(a) for a in sheet["articles"]] + [0])
    out = {"article": [a["id"] for a in sheet["articles"]], "wording": [t["whole"]] + [str(i) for i in range(1, most + 1)],
           "stance": list(t["stances"])}
    if position["party"] == sheet["persona"]["id"]:
        out["firm_limit"] = sorted(t["firm_values"])
    return {k: v for k, v in out.items() if len(v) >= 2 or k == "stance"}


def constraint_of(sheet, position, t):
    """D-799: the reply object one question may produce, for the pass's logits constraint
    (neg_synth_label_pass.LabelGrammar): the fixed key order, the sheet's article ids, the stances, the firm-limit
    values (the persona's own statements both, every other statement the one the template asks for, the value
    mapped to false), and each article's own count of bracketed wordings, counted here as read_wording counts it.
    Option sets and counts only, never an answer."""
    persona = position["party"] == sheet["persona"]["id"]
    firm = sorted(t["firm_values"]) if persona else sorted(k for k, v in t["firm_values"].items() if v is False)
    return {"schema": lp.CONSTRAINT_SCHEMA, "order": list(lp.FIELDS),
            "values": {"article": [a["id"] for a in sheet["articles"]], "stance": list(t["stances"]),
                       "firm_limit": firm},
            "wording": {"whole": t["whole"], "per_article": {a["id"]: _wordings(a) for a in sheet["articles"]}}}


def build_pass(sheet_paths, expected, out, cfg):
    """The labelling pass's prompts file: each sheets file held to the SHA-256 role S handed over, checked
    (an answer field refuses it unread), and every position's question rendered here, on the laptop."""
    t = load_template(cfg)
    sets, prompts = {}, []
    for path in sheet_paths:
        name = set_of(path)
        if name in sets:
            raise ValueError("refused: a set is named twice")
        digest = _file_sha(path)
        if expected.get(name) != digest:
            raise ValueError("refused: the sheets file of %s does not have the SHA-256 role S handed over" % name)
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        sheets = check_sheets(value)
        n0 = len(prompts)
        for s in sheets:
            for p in s["positions"]:
                text = render(s, p, t)
                prompts.append({"prompt_id": "%s-%05d" % (name, len(prompts) - n0 + 1), "set": name,
                                "item_id": s["item_id"], "position_id": p["id"], "prompt": text,
                                "prompt_sha256": lp._sha(text), "answers": declared_answers(s, p, t),
                                "constraint": constraint_of(s, p, t)})
        sets[name] = {"file_sha256": digest, "sheets_sha256": ns._sha(value), "items": len(sheets),
                      "positions": len(prompts) - n0}
    if set(expected) != set(sets):
        raise ValueError("refused: the expected digests name other sets than the sheets given")
    template_sha = hashlib.sha256((ROOT / cfg["labeller"]["template"]).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    target = ns.na.outside_repository(out)
    return lp.write_file(target, cfg["labeller"], cfg["generation"]["generator_family"], template_sha, sets, prompts)


class Evidence:
    """Bytes by relative path from a fetched evidence folder or a collected_evidence tar.gz, nothing extracted."""

    def __init__(self, path):
        import tarfile
        self.path = Path(path)
        self.tar = tarfile.open(self.path, "r:*") if self.path.is_file() else None
        if self.tar:
            self.names = {m.name.lstrip("./"): m for m in self.tar.getmembers() if m.isfile()}
        else:
            self.names = {p.relative_to(self.path).as_posix(): p for p in self.path.rglob("*") if p.is_file()}

    def read(self, name):
        if self.tar:
            return self.tar.extractfile(self.names[name]).read()
        return self.names[name].read_bytes()


def pass_replies(evidence, prompts_path):
    """(measurement, {prompt_id: reply text}) of the one labelling pass in the evidence that asked this prompts
    file: every row's reply held to the SHA-256 the pass recorded, one ok record per prompt, no other record."""
    digest = _file_sha(prompts_path)
    found = []
    for name in evidence.names:
        if name.endswith("/" + lp.MEASUREMENT_FILE) or name == lp.MEASUREMENT_FILE:
            try:
                m = json.loads(evidence.read(name))
            except ValueError:
                continue
            if isinstance(m, dict) and m.get("schema") == lp.MEASUREMENT_SCHEMA:
                found.append((name, m))
    if len(found) != 1:
        raise ValueError("refused: the evidence holds %d labelling measurements, not one" % len(found))
    name, m = found[0]
    if m["prompts_file_sha256"] != digest:
        raise ValueError("refused: the evidence's labelling pass asked another prompts file")
    folder = name[: -len(lp.MEASUREMENT_FILE)] + "audit/model_replies/"
    records = {}
    for rec_name in sorted(n for n in evidence.names if n.startswith(folder) and n.endswith(".json")):
        r = json.loads(evidence.read(rec_name))
        if r.get("doc_id") in records or not r.get("backend_ok") or (r.get("reply") or {}).get("text") is None:
            raise ValueError("refused: a prompt has two records, or a record is not a saved reply")
        records[r["doc_id"]] = r
    rows = {row["prompt_id"]: row for row in m["rows"]}
    decisions = {}
    if set(records) != set(rows) or len(rows) != m["prompts"]:
        raise ValueError("refused: the reply records are not one per prompt")
    replies = {}
    for pid, row in rows.items():
        text = records[pid]["reply"]["text"]
        if lp._sha(text) != row["reply_sha256"] or records[pid]["call_id"] != row["call_id"]:
            raise ValueError("refused: a saved reply differs from the digest its pass recorded")
        fields = ((records[pid].get("decision") or {}).get("fields")) or {}
        if lp._sha(json.dumps(fields, sort_keys=True)) != row.get("decisions_sha256"):
            raise ValueError("refused: a saved decision differs from the digest its pass recorded")
        replies[pid] = text
        decisions[pid] = fields
    return m, replies, decisions


def read_pass(prompts_path, sheets_path, evidence_path, cfg):
    """(labels file, labeller record) of one set from the fetched evidence: the sheets held to the digest the
    prompts file carries, each reply read once by answer_form, counted by reason."""
    t = load_template(cfg)
    value = lp.read_file(prompts_path)
    prompts = lp.check_file(value)
    name = set_of(sheets_path)
    if name not in value["sets"] or _file_sha(sheets_path) != value["sets"][name]["file_sha256"]:
        raise ValueError("refused: the sheets file is not the one the pass was built from")
    sheet_value = json.loads(Path(sheets_path).read_text(encoding="utf-8"))
    by_id = {s["item_id"]: s for s in check_sheets(sheet_value)}
    measurement, replies, decisions = pass_replies(Evidence(evidence_path), prompts_path)
    jobs, texts, confidence = [], [], {}
    for p in (q for q in prompts if q["set"] == name):
        sheet = by_id[p["item_id"]]
        position = next(x for x in sheet["positions"] if x["id"] == p["position_id"])
        if render(sheet, position, t) != p["prompt"]:
            raise ValueError("refused: a question differs from the one the declared template renders")
        jobs.append((sheet, position))
        texts.append(replies[p["prompt_id"]])
        confidence.setdefault(p["item_id"], {})[p["position_id"]] = {
            "confidence": lp.confidence_of(decisions[p["prompt_id"]]), "fields": decisions[p["prompt_id"]]}
    labels, reasons = read_replies(jobs, texts, t)
    for s in by_id:
        labels.setdefault(s, {})
    record = {"schema": RECORD_SCHEMA, "family": cfg["labeller"]["family"], "model_id": measurement["model_id"],
              "revision": measurement["revision"], "decoding": measurement["decoding"],
              "template_sha256": value["template_sha256"], "sheets_sha256": ns._sha(sheet_value),
              "sheets_file_sha256": value["sets"][name]["file_sha256"], "items": len(by_id),
              "positions": len(jobs), "by_reason": dict(reasons), "at_allowance": sum(
                  1 for r in measurement["rows"] if r["set"] == name and r["new_tokens"] >= int(
                      measurement["decoding"]["max_new_tokens"])),
              "prompts_file_sha256": measurement["prompts_file_sha256"], "route": "replay pass, sealed B1",
              "labelled_at": measurement["finished_at"], "read_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    record["confidence_read"] = sum(1 for v in confidence.values() for c in v.values() if c["confidence"] is not None)
    # D-799: the set's constrained replies by outcome, as the pass recorded them (a v1 pass has none).
    outcomes = Counter(r["constraint_outcome"] for r in measurement["rows"]
                       if r["set"] == name and "constraint_outcome" in r)
    record["constraint_by_reason"] = dict(outcomes) if value["schema"] == lp.SCHEMA_V2 else None
    return {"schema": LABELS_SCHEMA, "labels": labels, "confidence": confidence}, record


def _expected(values):
    out = {}
    for v in values or []:
        name, _, digest = v.partition("=")
        if not lp.SET_NAME.match(name) or len(digest) != 64:
            raise SystemExit("--expect takes SET=SHA256")
        out[name] = digest.lower()
    return out


def refuse_existing(paths):
    """A second reading of the same saved replies goes to new names: an output that exists refuses the read
    before anything is read or written (lane/label-wording-reader), so an earlier reading is never overwritten."""
    for target in paths:
        if target and Path(target).exists():
            raise SystemExit("refused: %s exists already (nothing is overwritten)" % Path(target).name)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--sheets", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--record", required=True)
    b = sub.add_parser("build-pass")
    b.add_argument("--sheets", action="append", required=True)
    b.add_argument("--expect", action="append", required=True, help="SET=SHA256 of each sheets file, from role S")
    b.add_argument("--out", required=True)
    r = sub.add_parser("read-pass")
    r.add_argument("--prompts", required=True)
    r.add_argument("--sheets", required=True)
    r.add_argument("--evidence", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--record", required=True)
    r.add_argument("--confidence", default=None, help="the per-label probabilities (role V's side only, never printed)")
    args = ap.parse_args(argv)
    cfg = ns.load_config()
    if args.cmd == "build-pass":
        value = build_pass(args.sheets, _expected(args.expect), args.out, cfg)
        print(json.dumps({"prompts": value["prompt_count"], "prompts_file_sha256": _file_sha(args.out),
                          "sets": {k: {f: v[f] for f in ("items", "positions", "file_sha256")}
                                   for k, v in value["sets"].items()}}, sort_keys=True))
        return 0
    if args.cmd == "read-pass":
        refuse_existing((args.out, args.record, args.confidence))
        labels, record = read_pass(args.prompts, args.sheets, args.evidence, cfg)
        ns._write_json(Path(args.out), labels["labels"])
        ns._write_json(Path(args.record), record)
        if args.confidence:
            ns._write_json(Path(args.confidence), {"schema": CONFIDENCE_SCHEMA, "set": set_of(args.sheets),
                                                   "field": lp.CONFIDENCE_FIELD, "positions": labels["confidence"]})
        print(json.dumps({k: record[k] for k in ("family", "model_id", "items", "positions", "by_reason",
                                                 "at_allowance", "confidence_read", "constraint_by_reason")},
                         sort_keys=True))
        return 0
    value = json.loads(Path(args.sheets).read_text(encoding="utf-8"))
    labels, record = run(value, cfg)
    ns._write_json(Path(args.out), labels["labels"])
    ns._write_json(Path(args.record), record)
    print(json.dumps({k: record[k] for k in ("family", "model_id", "items", "positions", "by_reason")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
