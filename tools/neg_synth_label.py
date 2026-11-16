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
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import neg_synth as ns  # noqa: E402
import answer_form as af  # noqa: E402

TEMPLATE_SCHEMA = "neg-synth-labeller-v1"
LABELS_SCHEMA = "neg-synth-labels-v1"
RECORD_SCHEMA = "neg-synth-labeller-record-v1"
# Fields a label sheet must never carry: what would let the labeller copy its answer.
ANSWER_FIELDS = ("stance", "article", "proposal", "red_lines", "red_line", "next_articles", "fate", "hidden",
                 "declared_key")


def load_template(cfg):
    t = json.loads((ROOT / cfg["labeller"]["template"]).read_text(encoding="utf-8"))
    if t.get("schema") != TEMPLATE_SCHEMA:
        raise ValueError("the labeller template's schema is not %s" % TEMPLATE_SCHEMA)
    return t


def check_model(model_id, cfg):
    """The labeller's model: a family the system under test and the generator never use, a bare id."""
    lab = cfg["labeller"]
    mid = str(model_id or "").strip()
    low = mid.lower()
    if not mid:
        raise ValueError("refused: no labeller model resolved")
    if any(f in low for f in lab["families_never_labeller"]) or cfg["generation"]["generator_family"] in low:
        raise ValueError("refused: a family of the system under test or of the generator never labels")
    if lab["family"] not in low:
        raise ValueError("refused: the labeller's family is declared as %s" % lab["family"])
    if ns._DATED.search(mid):
        raise ValueError("refused: a dated snapshot id; a bare repository id read live is recorded")
    return mid


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
             "example": json.dumps(t["example"], ensure_ascii=False)}
    out = t["template"]
    for name, value in fills.items():
        out = out.replace("{" + name + "}", value)
    return out


def _wordings(article):
    return len([s for s in ns.sna.bracket_spans(article["text"]) if s.strip()])


def read_answer(reply, sheet, position, t):
    """(label, None) or (None, reason): the reply read once by answer_form, every value against the sheet's own
    ids and the declared values."""
    obj, why, _several = af.last_object(reply)
    if why:
        return None, why
    arts = {a["id"]: a for a in sheet["articles"]}
    article, why = af.match(obj.get("article"), sorted(arts))
    if why:
        return None, "article:" + why
    n = _wordings(arts[article])
    wording, why = af.match(obj.get("wording"), [t["whole"]] + [str(i) for i in range(1, n + 1)])
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--sheets", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--record", required=True)
    args = ap.parse_args(argv)
    cfg = ns.load_config()
    value = json.loads(Path(args.sheets).read_text(encoding="utf-8"))
    labels, record = run(value, cfg)
    ns._write_json(Path(args.out), labels["labels"])
    ns._write_json(Path(args.record), record)
    print(json.dumps({k: record[k] for k in ("family", "model_id", "items", "positions", "by_reason")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
