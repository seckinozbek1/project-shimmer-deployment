#!/usr/bin/env python3
"""B1 and the cloud reference on the negotiation features (D-S102 item 8).

docs/loop/stages/NEGOTIATION_MEASUREMENT_PLAN.md sections 3.1 and 4.2. Two forms, fixed in
`negotiation_b1_prompt.json` before any reply:

- `movement`: one item per issue and pair of consecutive rounds. The four declared quotes (both
  parties, both rounds, from the case manifest's sources, the same the system reads; a silent slot
  says so), the issue's declared unit where there is one, one question, four declared answers.
- `suggestion`: one item per open issue for the supported party. The system's own question
  (`case_questions.suggestion_question`, config/case_questions.json) asked over the whole last round
  (every passage of every last-round document, with the parties' stated positions on the issue in
  every round), where the system asks over its own selection. So every arm's reply is read by the
  same Python checks, `case_questions.read_suggestion`, against the passages its question showed.

    build  --case <case folder> [...] --out <prompts.json>     the prompts file (no model)
    run    --prompts <prompts.json> --out <pass folder>        every prompt through B1 (a GPU)
    answers --prompts <prompts.json> --run <pass folder> --out <answers.json>

A prompts file holds each prompt's inputs, so `load_prompts` renders every prompt again and holds it
to its SHA-256. `answers` reads the pass's reply records: a movement reply becomes one of the four
labels or `no_answer`; a suggestion reply becomes `read_suggestion`'s kept item or its refusal. The
scorer, tools/score_negotiation.py, reads the answers file. Development, exposed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "scripts"
for _p in (str(SCRIPTS), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CONFIG_PATH = HERE / "negotiation_b1_prompt.json"
CONFIG_SCHEMA = "negotiation-b1-prompt-v1"
SCHEMA = "negotiation-b1-prompts-v1"
ANSWERS_SCHEMA = "negotiation-answers-v1"
MEASUREMENT_SCHEMA = "negotiation-b1-measurement-v1"
MEASUREMENT_FILE = "replay_measurement.json"
LABELS = ("moved_toward", "moved_away", "unchanged_from_prior", "not_computable")
NO_ANSWER = "no_answer"
FORMS = ("movement", "suggestion")
AGENT_LABEL = "NEGOTIATION_B1"
PHASE = "NEGOTIATION"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _norm(text):
    text = " ".join(str(text or "").lower().split())
    return text[:-1].rstrip() if text.endswith(".") else text


# ---------------------------------------------------------------------------
# the config


def check_config(value):
    if not isinstance(value, dict) or value.get("schema") != CONFIG_SCHEMA:
        raise ValueError("not a negotiation B1 prompt config (%s)" % CONFIG_SCHEMA)
    m = value.get("movement")
    if not isinstance(m, dict) or not isinstance(m.get("template"), str):
        raise ValueError("the config declares a movement template")
    for slot in ("{issue}", "{unit}", "{quotes}", "{answer_lines}"):
        if m["template"].count(slot) != 1:
            raise ValueError("the movement template fills %s once" % slot)
    if "{unit_value}" not in str(m.get("unit_declared")) or not isinstance(m.get("unit_none"), str) \
            or not isinstance(m.get("silent"), str) or not all(s in str(m.get("quote_line")) for s in ("{actor}", "{round}", "{quote}")):
        raise ValueError("the movement form declares its unit lines, its silent slot and its quote line")
    answers = m.get("answers")
    if not isinstance(answers, list) or sorted(a.get("label") for a in answers) != sorted(LABELS):
        raise ValueError("the movement form declares the four labels once each")
    seen = set()
    for a in answers:
        accepted = {_norm(x) for x in a.get("accepted") or []}
        if not isinstance(a.get("value"), str) or _norm(a["value"]) not in accepted or accepted & seen \
                or not isinstance(a.get("line"), str):
            raise ValueError("each answer accepts its own value, and no spelling twice")
        seen |= accepted
    if type(m.get("max_new_tokens")) is not int or m["max_new_tokens"] <= 0:
        raise ValueError("the movement form declares a positive max_new_tokens")
    if (value.get("suggestion") or {}).get("from") != "config/case_questions.json":
        raise ValueError("the suggestion form is the system's own question (config/case_questions.json)")
    groups = value.get("models")
    if not isinstance(groups, list) or not groups or len({g.get("group") for g in groups}) != len(groups):
        raise ValueError("the config declares its model groups once each")
    for g in groups:
        if not (isinstance(g.get("group"), str) and g.get("backend") in ("local_auditor", "local_producer")
                and isinstance(g.get("agent"), str) and g.get("checkpoint") in ("base", "tuned")):
            raise ValueError("a model group needs a name, a local backend, an agent and a checkpoint")
    return value


def load_config(path=CONFIG_PATH):
    return check_config(json.loads(Path(path).read_text(encoding="utf-8")))


def suggestion_config():
    """config/case_questions.json, the system's own suggestion block and all."""
    import case_questions
    return case_questions.load_config()


# ---------------------------------------------------------------------------
# a case, as a run reads it


def read_case(case_dir):
    """(manifest, documents) of a case folder in the sealer's workload layout: the manifest and
    every context file, read as text with LF line ends."""
    case_dir = Path(case_dir)
    manifest = json.loads((case_dir / "case_manifest.json").read_text(encoding="utf-8"))
    documents = []
    for path in sorted((case_dir / "context").iterdir()):
        if path.is_file() and not path.name.startswith("_"):
            import text_extract
            documents.append({"id": path.stem, "name": path.name,
                              "text": text_extract.extract_text(path).replace("\r\n", "\n")})
    return manifest, documents


def bound_record(manifest, documents):
    """{manifest, evidence}: the declared sources bound to the documents, as the case phase binds them."""
    import multi_round as mr
    from reference_builder import ReferenceIndex
    checked = mr.validate_manifest(manifest)
    with tempfile.TemporaryDirectory(prefix="shimmer_negotiation_") as td:
        refs = ReferenceIndex.open(Path(td), index_path=Path(td) / "reference_index.json")
        evidence = mr.bind_sources(checked, documents, refs)
    return {"manifest": checked, "evidence": evidence}


def _rounds(manifest):
    return [r["round_id"] for r in sorted(manifest["rounds"], key=lambda r: r["sequence"])]


def movement_items(manifest):
    """One item per declared issue and pair of consecutive rounds: the four slots (each party in
    each round), each holding that party's declared quotes on the issue in that round, or None."""
    rounds = _rounds(manifest)
    actors = [a["actor_id"] for a in manifest["actors"]]
    out = []
    for issue in manifest["issues"]:
        for before, after in zip(rounds, rounds[1:]):
            slots = []
            for rnd in (before, after):
                for actor in actors:
                    quotes = [s["quote"] for s in manifest["sources"] if s["issue_id"] == issue["issue_id"]
                              and s["round_id"] == rnd and s["actor_id"] == actor and s["state"] == "accepted"]
                    slots.append({"actor": actor, "round": rnd, "quote": " ".join(quotes) if quotes else None})
            out.append({"case_id": manifest["case_id"], "issue_id": issue["issue_id"], "rounds": [before, after],
                        "unit": issue.get("unit"), "slots": slots})
    return out


def render_movement(config, item):
    m = config["movement"]
    unit = (m["unit_declared"].replace("{unit_value}", item["unit"]) if item.get("unit") else m["unit_none"])
    quotes = "\n".join(m["quote_line"].replace("{actor}", s["actor"]).replace("{round}", s["round"])
                       .replace("{quote}", s["quote"] if s["quote"] is not None else m["silent"]) for s in item["slots"])
    lines = "\n".join(a["line"] for a in m["answers"])
    slots = {"{issue}": item["issue_id"], "{unit}": unit, "{quotes}": quotes, "{answer_lines}": lines}
    # One pass over the template, so a quote holding a slot's name is never read as a slot.
    out, rest = [], m["template"]
    while True:
        hits = [(rest.find(k), k) for k in slots if rest.find(k) >= 0]
        if not hits:
            out.append(rest)
            return "".join(out)
        at, key = min(hits)
        out.append(rest[:at] + slots[key])
        rest = rest[at + len(key):]


def whole_round_selection(record, documents, party, issue):
    """The system's selection with every passage of the last round in place of the issue's declared
    units: the stated positions in round order, then each last-round document's passages and table rows."""
    import case_questions as cq
    widened = dict(issue)
    last = max(record["manifest"]["rounds"], key=lambda r: r["sequence"])
    import pairing_map
    every = []
    docs = {d["id"]: d for d in documents}
    for doc_id in last.get("document_ids") or []:
        if doc_id in docs:
            every += [u["unit_id"].split("-", 1)[-1] for u in pairing_map.split_units(docs[doc_id]["text"], document_id=doc_id)]
    widened["text_units"] = sorted(set(every))
    return cq.selection(record, documents, party, widened)


def suggestion_items(record, documents):
    import case_questions as cq
    party = cq.supported_party(record["manifest"])
    if party is None:
        return []
    return [whole_round_selection(record, documents, party, issue) for issue in cq.open_issues(record["manifest"])]


def render_suggestion(sconfig, chosen):
    import case_questions as cq
    return cq.suggestion_question(chosen, sconfig)["text"]


# ---------------------------------------------------------------------------
# the prompts file


def build(case_dirs, out, *, config_path=CONFIG_PATH):
    config = load_config(config_path)
    sconfig = suggestion_config()
    prompts = []
    for case_dir in case_dirs:
        manifest, documents = read_case(case_dir)
        record = bound_record(manifest, documents)
        for group in config["models"]:
            for item in movement_items(record["manifest"]):
                user = render_movement(config, item)
                prompts.append(dict(group, prompt_id="m%04d" % (len(prompts) + 1), form="movement",
                                    case_id=item["case_id"], issue_id=item["issue_id"], rounds=item["rounds"],
                                    item=item, user=user, user_sha256=_sha(user), system=None,
                                    max_new_tokens=config["movement"]["max_new_tokens"]))
            for chosen in suggestion_items(record, documents):
                user = render_suggestion(sconfig, chosen)
                prompts.append(dict(group, prompt_id="s%04d" % (len(prompts) + 1), form="suggestion",
                                    case_id=record["manifest"]["case_id"], issue_id=chosen["issue_id"],
                                    chosen=chosen, user=user, user_sha256=_sha(user), system=None,
                                    max_new_tokens=sconfig["suggestion"]["max_new_tokens"]))
    value = {"schema": SCHEMA, "config": config, "config_sha256": _sha(_canonical(config)),
             "suggestion": sconfig["suggestion"], "suggestion_sha256": _sha(_canonical(sconfig["suggestion"])),
             "prompt_count": len(prompts), "prompts": prompts}
    _write_json(out, value)
    return value


def is_prompts_file(value):
    return isinstance(value, dict) and value.get("schema") == SCHEMA


def load_prompts(path):
    """The prompts, each rendered again from its own inputs and held to its SHA-256."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not is_prompts_file(value) or not isinstance(value.get("prompts"), list) or not value["prompts"]:
        raise ValueError("not a negotiation B1 prompts file (%s)" % SCHEMA)
    config = check_config(value.get("config"))
    if value.get("config_sha256") != _sha(_canonical(config)):
        raise ValueError("the prompts file's config does not match its SHA-256")
    if value.get("suggestion_sha256") != _sha(_canonical(value.get("suggestion"))):
        raise ValueError("the prompts file's suggestion block does not match its SHA-256")
    if value.get("prompt_count") != len(value["prompts"]):
        raise ValueError("the prompts file's count is wrong")
    groups = {g["group"]: g for g in config["models"]}
    sconfig = {"suggestion": value["suggestion"]}
    ids, keys = set(), set()
    for p in value["prompts"]:
        g = groups.get(p.get("group"))
        if g is None or any(p.get(k) != g[k] for k in ("backend", "agent", "checkpoint")):
            raise ValueError("a prompt names a model group its config does not declare: %s" % p.get("prompt_id"))
        if p.get("form") == "movement":
            user = render_movement(config, p["item"])
            key = (p["group"], p["case_id"], p["issue_id"], tuple(p["rounds"]), "movement")
        elif p.get("form") == "suggestion":
            user = render_suggestion(sconfig, p["chosen"])
            key = (p["group"], p["case_id"], p["issue_id"], "suggestion")
        else:
            raise ValueError("a prompt names a form this file does not declare: %s" % p.get("prompt_id"))
        if p.get("user") != user or p.get("user_sha256") != _sha(user) or p.get("system") is not None:
            raise ValueError("a prompt is not its template's rendering: %s" % p.get("prompt_id"))
        if p["prompt_id"] in ids or key in keys:
            raise ValueError("a prompt id, or a (group, case, issue, form), repeats")
        ids.add(p["prompt_id"])
        keys.add(key)
    return value["prompts"]


def read_file(path):
    load_prompts(path)
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# replies


def parse_movement(reply, config):
    """One of the four labels, or no_answer: the reply's normalised spelling against `accepted`."""
    if not isinstance(reply, str) or not reply.strip():
        return NO_ANSWER
    said = _norm(reply)
    for a in config["movement"]["answers"]:
        if said in {_norm(x) for x in a["accepted"]}:
            return a["label"]
    return NO_ANSWER


def read_suggestion(reply, chosen, sconfig):
    """(item, None) or (None, why), by the system's own reader."""
    import case_questions as cq
    if not isinstance(reply, str) or not reply.strip():
        return None, "no_reply"
    return cq.read_suggestion(reply, chosen, sconfig)


def answers_from_texts(value, texts):
    """{schema, rows}: each prompt's answer from its reply text (`texts`, prompt id to text or None)."""
    config = value["config"]
    sconfig = {"suggestion": value["suggestion"]}
    rows = []
    for p in value["prompts"]:
        text = texts.get(p["prompt_id"])
        row = {"prompt_id": p["prompt_id"], "group": p["group"], "form": p["form"], "case_id": p["case_id"],
               "issue_id": p["issue_id"]}
        if p["form"] == "movement":
            row.update(rounds=p["rounds"], label=parse_movement(text, config))
        else:
            item, why = read_suggestion(text, p["chosen"], sconfig)
            row.update(kept=item is not None, refusal=why,
                       suggested_wording=(item or {}).get("suggested_wording"), quote=(item or {}).get("quote"),
                       checks=(item or {}).get("checks"))
        rows.append(row)
    return {"schema": ANSWERS_SCHEMA, "prompts_sha256": value.get("_sha256"), "rows": rows}


def answers(prompts_path, run_dir, out=None):
    import reply_records
    value = read_file(prompts_path)
    value["_sha256"] = hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest()
    run_dir = Path(run_dir)
    measurement = json.loads((run_dir / MEASUREMENT_FILE).read_text(encoding="utf-8"))
    if measurement.get("schema") != MEASUREMENT_SCHEMA or measurement.get("prompts_sha256") != value["_sha256"]:
        raise ValueError("the pass folder is not a negotiation B1 pass of these prompts")
    records = {r.get("call_id"): r for r in reply_records.records(run_dir / "audit" / "model_replies")}
    texts = {}
    for row in measurement.get("rows") or []:
        record = records.get(row.get("call_id")) or {}
        reply = record.get("reply") or {}
        texts[row["prompt_id"]] = (reply.get("text") if isinstance(reply, dict) and record.get("backend_ok") else None)
    result = answers_from_texts(value, texts)
    if out:
        _write_json(out, result)
    return result


# ---------------------------------------------------------------------------
# run (one GPU, the bare model)


def make_backend(reader, context):
    import bare_model
    return bare_model.LocalBackend(reader, context)


def run(prompts_path, out, *, backend_factory=None, reader_for=None, run_id=None):
    """Every prompt through its group's bare model, one reply record each; the measurement file is
    written after every prompt, so a stopped pass stays readable."""
    import bare_model
    import decoding_policy
    import final_models
    import reply_records
    value = read_file(prompts_path)
    prompts, config = value["prompts"], value["config"]
    out = Path(out)
    context = bare_model.RunContext(out, run_id or ("negotiation-" + uuid.uuid4().hex[:12]))
    factory = backend_factory or make_backend
    rows, models = [], {}
    sha = hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest()

    def snapshot(complete):
        return {"schema": MEASUREMENT_SCHEMA, "run_id": context.run_id, "complete": complete, "prompts": len(prompts),
                "prompts_sha256": sha, "config_sha256": value["config_sha256"], "models": models,
                "seconds": round(sum(r["seconds"] or 0 for r in rows), 3), "rows": rows,
                "reads": "ids, counts and seconds only here; the replies in the reply records"}
    for group in config["models"]:
        mine = [p for p in prompts if p["group"] == group["group"]]
        if not mine:
            continue
        allowance = max(int(p["max_new_tokens"]) for p in mine)
        reader = (reader_for(group, allowance) if reader_for is not None else
                  bare_model.resolve_reader(agent=group["agent"], checkpoint=group["checkpoint"], max_new_tokens=allowance))
        if final_models.mode() == "final":
            final_models.verify_runtime()
        backend = factory(reader, context)
        try:
            loaded = backend.prepare()
            models[group["group"]] = {"model_id": loaded.get("model_id"), "digest": loaded.get("digest"),
                                      "backend": reader["backend"], "agent": reader["agent"]}
            limit = backend.max_context()
            for p in mine:
                tokens = int(backend.count_prompt(None, p["user"]))
                row = {"prompt_id": p["prompt_id"], "form": p["form"], "group": group["group"], "prompt_tokens": tokens,
                       "max_new_tokens": int(p["max_new_tokens"]), "failure": None, "seconds": None}
                result, error = {}, ""
                if tokens + int(p["max_new_tokens"]) > int(limit):
                    row["failure"] = error = "prompt_over_context"
                else:
                    started = time.perf_counter()
                    result = backend.generate(None, p["user"], int(p["max_new_tokens"])) or {}
                    row["seconds"] = round(time.perf_counter() - started, 3)
                text = result.get("text") if isinstance(result.get("text"), str) else None
                decoding = dict(decoding_policy.usage_fields(reader["decoding"]), max_new_tokens=int(p["max_new_tokens"]))
                call = reply_records.write(context, agent=AGENT_LABEL, backend=reader["backend"], model_id=reader["model_id"],
                                           model_mode=reader.get("model_mode"), payload=result.get("payload"),
                                           payload_form=result.get("form"), reply=text, ok=not error, error=error,
                                           decoding=decoding, sensitive=False, phase=PHASE, doc_id=p["case_id"],
                                           attention=result.get("attention"), prefill=result.get("prefill"))
                if not call:
                    raise RuntimeError("the reply record for prompt %s could not be written" % p["prompt_id"])
                row["call_id"] = call
                rows.append(row)
                _write_json(out / MEASUREMENT_FILE, snapshot(False))
        finally:
            release = getattr(backend, "release", None)
            if callable(release):
                release()
    result = snapshot(True)
    _write_json(out / MEASUREMENT_FILE, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", allow_abbrev=False)
    b.add_argument("--case", action="append", required=True, type=Path)
    b.add_argument("--out", required=True, type=Path)
    r = sub.add_parser("run", allow_abbrev=False)
    r.add_argument("--prompts", required=True, type=Path)
    r.add_argument("--out", required=True, type=Path)
    a = sub.add_parser("answers", allow_abbrev=False)
    a.add_argument("--prompts", required=True, type=Path)
    a.add_argument("--run", required=True, type=Path)
    a.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "build":
        value = build(args.case, args.out)
        print(json.dumps({"prompts": value["prompt_count"]}))
    elif args.command == "run":
        result = run(args.prompts, args.out)
        print(json.dumps({"prompts": result["prompts"], "seconds": result["seconds"]}))
    else:
        result = answers(args.prompts, args.run, args.out)
        print(json.dumps({"rows": len(result["rows"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
