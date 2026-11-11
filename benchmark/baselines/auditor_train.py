"""The auditor backend's training pass (D-S57 item 3): a LoRA adapter for the rule check, then its
development questions.

Development, exposed. Not an arm and not a review. It rides the ordinary final runner's replay pass,
as judge_train.py does: replay_prompts.py hands an `auditor-training-session-v1` file here, so every
launch rule (ledger, guard, reaper, caps, seal) stands and no bound controller file changes.

  assemble (no model)
      py -3.12 benchmark/baselines/auditor_train.py assemble --rows-dir R --mix dev_mix|permissive_mix
          --questions Q --model-id ID --revision REV --max-updates U --max-train-seconds S
          --checkpoint trained_half=0.5 --checkpoint trained_full=1 --passes base,trained_half,trained_full --out F
    One recipe: tools/build_auditor_training.py's rows and held-out rows of one mix, its manifest,
    tools/build_auditor_questions.py's development questions as the exact bytes of their file, the
    checkpoints and passes fixed before training. The rows, the questions and the shipped question
    (config/auditor_questions.json `rule_check`) must carry one question digest.

  session (no model)
      py -3.12 benchmark/baselines/auditor_train.py session --dev F1 --permissive F2 --out F
    Both recipes for ONE instance session, refused unless they differ in their rows alone.

  run (the rented machine, through replay_prompts.py run --prompts F --out D --paths sdpa)
    For each recipe: judge_train.train, unchanged (the Producer's recipe: 4-bit base, rank 8, one
    answer token, 16 rows an update, the schedule cut to max_train_seconds at the measured rate),
    under D/<mix>/training/ (the last recipe's under D/training/); then one pass per name of
    `question_passes` over the development questions, each question decided by
    bare_model.LocalBackend.choose, which renders and scores exactly as agent_wrapper.call_choice
    does (one user turn through the model's own chat template, choice_decision.bind, one forward
    pass, pinned attention), with the pass's adapter on the base. The last recipe's last pass
    writes one reply record per question under D, where the runner counts; every other pass under
    D/passes/<mix>/<name>. Each pass writes its decisions (labels, probabilities, ids; no text) to
    its folder's decisions.jsonl and D/replay_measurement.json sums them. No threshold is applied:
    calibration reads half A, the measurement half B, after the run, on the saved probabilities.

The base is the auditor backend's own (unsloth/Phi-3.5-mini-instruct-bnb-4bit, the model every
local_auditor role runs on), so a trained adapter is that backend's, and the publication rule of
judge_train.PUBLICATION (the operator's, D-281) is carried into every adapter folder.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (HERE, ROOT / "scripts", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import judge_train  # noqa: E402

SCHEMA = "auditor-training-v1"
SESSION_SCHEMA = "auditor-training-session-v1"
QUESTIONS_SCHEMA = "auditor-rule-check-questions-v1"
FORM = "rule_check"
AGENT = "PRACTICE_AUDITOR"
AGENT_LABEL = "AUDITOR_RULE_CHECK"
PHASE = "auditor_training"
BASE_PASS = judge_train.BASE_PASS
MEASUREMENT = "replay_measurement.json"
ROW_FIELDS = judge_train.ROW_FIELDS | {"tokens"}


def _sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def shipped_question():
    import auditor_questions
    return auditor_questions.load_config()[FORM]


def question_digest(question):
    import build_auditor_training
    return build_auditor_training.question_digest(question)


def forms_text(question):
    """The forms judge_train.train reads (`_forms`): the rule check's answers, nothing else."""
    return _canonical({"config": {"choice": {"forms": {FORM: {"answers": question["decision"]["answers"]}}}}})


def questions_of(value):
    return json.loads(value["questions_text"])


def recipe_digest(value):
    return _sha(_canonical({k: v for k, v in value.items() if k != "recipe_sha256"}))


def check(value):
    """`value` held to what run() needs, or ValueError. A session is each recipe so held, in order,
    under their one digest."""
    if isinstance(value, dict) and value.get("schema") == SESSION_SCHEMA:
        recipes = value.get("recipes") or []
        if [r.get("publication", {}).get("mix") for r in recipes] != list(judge_train.SESSION_ORDER):
            raise ValueError("a session holds dev_mix then permissive_mix")
        for recipe in recipes:
            check(recipe)
        if value.get("recipes_sha256") != pair_digest(*recipes):
            raise ValueError("the session is not its recipes digest")
        return value
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("not an auditor training file")
    if value["questions_sha256"] != _sha(value["questions_text"]):
        raise ValueError("the questions are not the declared ones")
    questions = questions_of(value)
    digest = value["question_sha256"]
    if questions.get("schema") != QUESTIONS_SCHEMA or questions.get("question_sha256") != digest \
            or value["data_manifest"].get("question_sha256") != digest:
        raise ValueError("the rows, the questions and the recipe ask different questions")
    labels = {a["label"] for a in json.loads(value["judge_prompts_text"])["config"]["choice"]["forms"][FORM]["answers"]}
    for side in ("rows", "held_out"):
        rows = value[side]
        if not rows or value[side + "_sha256"] != _sha(_canonical(rows)):
            raise ValueError("the %s are empty or not the declared ones" % side)
        for row in rows:
            if not ROW_FIELDS <= set(row) or row["form"] != FORM or row["answer"] not in labels:
                raise ValueError("a row lacks its form, its text or a fixed answer")
    if {r["row_id"] for r in value["rows"]} & {r["row_id"] for r in value["held_out"]} \
            or {r["user"] for r in value["rows"]} & {r["user"] for r in value["held_out"]}:
        raise ValueError("a row sits on both sides")
    if {q["user"] for q in questions["questions"]} & {r["user"] for side in ("rows", "held_out") for r in value[side]}:
        raise ValueError("a development question is a training row")
    for q in questions["questions"]:
        if q["answer"] not in labels or q["user_sha256"] != _sha(q["user"]):
            raise ValueError("a development question is not as declared")
    checkpoints = value["checkpoints"]
    fractions = list(checkpoints.values())
    if not 1 <= len(fractions) <= judge_train.MAX_CHECKPOINTS or not all(0 < f <= 1 for f in fractions) \
            or len(set(fractions)) != len(fractions) or max(fractions) != 1:
        raise ValueError("the checkpoints are the last and at most three earlier, each at a fraction of the schedule")
    passes = value["question_passes"]
    last = max(checkpoints, key=checkpoints.get)
    if not passes or passes[-1] != last or len(set(passes)) != len(passes) or not set(passes) <= set(checkpoints) | {BASE_PASS}:
        raise ValueError("the passes name base or a checkpoint once each, and end on the last checkpoint")
    publication = value["publication"]
    if publication != judge_train.PUBLICATION.get(publication.get("mix")):
        raise ValueError("the file does not state a declared mix and its publication rule")
    if publication["publishable"] and any(r["share_alike"] for side in ("rows", "held_out") for r in value[side]):
        raise ValueError("a publishable mix holds a share-alike row")
    training = value["training"]
    if training.get("max_updates", 0) <= 0 or training["max_updates"] * training["gradient_accumulation"] > len(value["rows"]) \
            or training.get("max_train_seconds", 0) <= 0:
        raise ValueError("the updates and the training time are stated and the rows hold them")
    if value["recipe_sha256"] != recipe_digest(value):
        raise ValueError("the file is not its recipe digest")
    return value


def read_file(path):
    return check(json.loads(Path(path).read_text(encoding="utf-8")))


def recipes_of(value):
    return value["recipes"] if value["schema"] == SESSION_SCHEMA else [value]


def load_prompts(path):
    """The questions the runner counts: the last recipe's, one reply record each."""
    return questions_of(recipes_of(read_file(path))[-1])["questions"]


def _rows(path):
    keep = sorted(ROW_FIELDS)
    return [{k: r[k] for k in keep} for r in map(json.loads, Path(path).read_text(encoding="utf-8").splitlines())]


def assemble(rows_dir, mix, questions_path, out, model_id, revision, max_updates, max_train_seconds, checkpoints, passes,
             question=None):
    question = question or shipped_question()
    rows_dir = Path(rows_dir)
    manifest = json.loads((rows_dir / "manifest.json").read_text(encoding="utf-8"))
    rows, held = _rows(rows_dir / ("%s_train.jsonl" % mix)), _rows(rows_dir / ("%s_held_out.jsonl" % mix))
    text = Path(questions_path).read_bytes().decode("utf-8")
    digest = question_digest(question)
    if manifest.get("question_sha256") != digest:
        raise ValueError("the rows were built on another question than the shipped rule check")
    value = {"schema": SCHEMA, "status": "development, exposed (D-S57 item 3, the auditor backend)",
             "training": dict(judge_train.RECIPE, model_id=model_id, revision=revision, max_train_seconds=max_train_seconds,
                              max_updates=max_updates),
             "publication": judge_train.PUBLICATION[mix], "checkpoints": dict(checkpoints), "question_passes": list(passes),
             "question_sha256": digest, "data_manifest": manifest,
             "rows": rows, "rows_sha256": _sha(_canonical(rows)), "held_out": held, "held_out_sha256": _sha(_canonical(held)),
             "judge_prompts_text": forms_text(question), "questions_text": text, "questions_sha256": _sha(text)}
    value["recipe_sha256"] = recipe_digest(value)
    check(value)
    Path(out).write_text(_canonical(value), encoding="utf-8", newline="\n")
    return value


def pair_digest(dev, loose):
    if (dev["publication"]["mix"], loose["publication"]["mix"]) != judge_train.SESSION_ORDER:
        raise ValueError("one dev_mix file and one permissive_mix file")
    for key in ("training", "checkpoints", "question_passes", "questions_sha256", "question_sha256", "judge_prompts_text"):
        if dev[key] != loose[key]:
            raise ValueError("the two recipes differ in more than their rows: " + key)
    return _sha("dev_mix:%s\npermissive_mix:%s\n" % (dev["recipe_sha256"], loose["recipe_sha256"]))


def session(dev_path, permissive_path, out):
    dev, loose = read_file(dev_path), read_file(permissive_path)
    value = {"schema": SESSION_SCHEMA, "status": "development, exposed (D-S57 item 3): one session, two recipes",
             "recipes": [dev, loose], "recipes_sha256": pair_digest(dev, loose)}
    check(value)
    Path(out).write_text(_canonical(value), encoding="utf-8", newline="\n")
    return value


def make_backend(reader, context):
    import bare_model
    return bare_model.LocalBackend(reader, context)


def reader_for(adapter):
    """The auditor backend's reader (bare_model.resolve_reader on PRACTICE_AUDITOR at its base
    checkpoint: the registry's local block, local_models.json, the frozen decoding policy), with
    the pass's adapter on it; None is the base model's pass."""
    import bare_model
    reader = bare_model.resolve_reader(agent=AGENT, checkpoint="base", max_new_tokens=1)
    return reader if adapter is None else dict(reader, adapter=adapter)


def ask(questions, answers, out, *, adapter=None, backend_factory=make_backend, reader=reader_for, run_id=None):
    """One pass: every question decided, one reply record each under `out`, and the decisions
    (labels, probabilities, ids; no text) in out/decisions.jsonl. Returns the pass summary."""
    import uuid
    import bare_model
    import reply_records
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    context = bare_model.RunContext(out, run_id or ("auditor-" + uuid.uuid4().hex[:12]))
    resolved = reader(adapter)
    backend = backend_factory(resolved, context)
    rows, failures, started = [], 0, time.perf_counter()
    try:
        loaded = backend.prepare()
        with open(out / "decisions.jsonl", "w", encoding="utf-8", newline="\n") as log:
            for q in questions:
                error, result = "", {}
                try:
                    result = backend.choose(None, q["user"], answers) or {}
                except Exception as exc:  # a named model failure is one question's, recorded, never retried
                    error = type(exc).__name__
                    failures += 1
                decision = result.get("decision")
                call = reply_records.write(context, agent=AGENT_LABEL, backend=resolved["backend"], model_id=resolved["model_id"],
                                           model_mode=resolved.get("model_mode"), payload=result.get("payload"),
                                           payload_form=result.get("form"), reply=None, ok=not error, error=error,
                                           decoding=dict(max_new_tokens=0), sensitive=False, phase=PHASE,
                                           doc_id=q["document_id"], attention=result.get("attention"),
                                           prefill=result.get("prefill"), decision=decision)
                if not call:
                    raise RuntimeError("the reply record for question %s could not be written" % q["question_id"])
                row = {"question_id": q["question_id"], "half": q["half"], "answer": q["answer"], "call_id": call,
                       "failure": error or None,
                       "probabilities": {a["label"]: a["probability"] for a in (decision or {}).get("answers") or []},
                       "top": (decision or {}).get("top"), "declared_mass": (decision or {}).get("declared_mass")}
                rows.append(row)
                log.write(json.dumps(row, sort_keys=True) + "\n")
    finally:
        release = getattr(backend, "release", None)
        if callable(release):
            release()
    right = {h: sum(1 for r in rows if r["half"] == h and r["top"] == r["answer"]) for h in ("A", "B")}
    counted = {h: sum(1 for r in rows if r["half"] == h) for h in ("A", "B")}
    return {"questions": len(rows), "failures": failures, "seconds": round(time.perf_counter() - started, 3),
            "model": {"model_id": loaded.get("model_id"), "digest": loaded.get("digest")},
            "top_answer_right": right, "by_half": counted, "adapter": adapter}


def run(prompts_path, out, *, paths=("sdpa",), decision=None, max_new_tokens=None, load=judge_train.load_model,
        backend_factory=make_backend, reader=reader_for):
    """The whole session: each recipe trained, then its passes; the last pass of the last recipe in D."""
    if list(paths) != ["sdpa"] or decision is not None or max_new_tokens is not None:
        raise ValueError("an auditor training pass runs the sdpa path alone, with no decision and no allowance")
    recipes = recipes_of(read_file(prompts_path))
    out = Path(out)
    summary = {"schema": "auditor-training-measurement-v1", "prompts_sha256": _sha(Path(prompts_path).read_bytes()),
               "recipes": [], "prompts": 0, "failures": 0, "seconds": 0.0}
    for number, value in enumerate(recipes):
        last_recipe = number == len(recipes) - 1
        mix = value["publication"]["mix"]
        place = out if last_recipe else out / mix
        result = judge_train.train(value, place / "training", load=load)
        _free()
        adapters = {a["group"]: {k: a[k] for k in ("path", "weights_sha256", "config_sha256")} for a in result["adapters"]}
        questions = questions_of(value)["questions"]
        answers = json.loads(value["judge_prompts_text"])["config"]["choice"]["forms"][FORM]["answers"]
        passes = {}
        for name in value["question_passes"]:
            target = out if (last_recipe and name == value["question_passes"][-1]) else out / "passes" / mix / name
            passes[name] = ask(questions, answers, target, adapter=adapters.get(name), backend_factory=backend_factory,
                               reader=reader)
            _free()
        summary["recipes"].append({"mix": mix, "recipe_sha256": value["recipe_sha256"], "training": {
            k: result.get(k) for k in ("updates", "planned_updates", "median_seconds_per_update", "first_loss", "last_loss",
                                       "schedule_cut", "memory")}, "held_out": result.get("held_out"), "passes": passes})
        summary["prompts"] = len(questions)
        summary["failures"] += sum(p["failures"] for p in passes.values())
        summary["seconds"] += sum(p["seconds"] for p in passes.values())
        (out / MEASUREMENT).write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return summary


def _free():
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("assemble")
    for name in ("--rows-dir", "--questions", "--out", "--model-id", "--revision", "--passes"):
        a.add_argument(name, required=True)
    a.add_argument("--mix", required=True, choices=sorted(judge_train.PUBLICATION))
    a.add_argument("--max-updates", type=int, required=True)
    a.add_argument("--max-train-seconds", type=float, required=True)
    a.add_argument("--checkpoint", action="append", required=True, help="name=fraction of the schedule")
    s = sub.add_parser("session")
    for name in ("--dev", "--permissive", "--out"):
        s.add_argument(name, required=True)
    args = parser.parse_args(argv)
    if args.command == "assemble":
        checkpoints = {k: float(v) for k, v in (c.split("=", 1) for c in args.checkpoint)}
        value = assemble(args.rows_dir, args.mix, args.questions, args.out, args.model_id, args.revision, args.max_updates,
                         args.max_train_seconds, checkpoints, [p for p in args.passes.split(",") if p])
        print(json.dumps({"recipe_sha256": value["recipe_sha256"], "rows": len(value["rows"]), "held_out": len(value["held_out"]),
                          "questions": len(questions_of(value)["questions"])}))
    else:
        value = session(args.dev, args.permissive, args.out)
        print(json.dumps({"recipes_sha256": value["recipes_sha256"], "prompts": len(load_prompts(args.out))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
