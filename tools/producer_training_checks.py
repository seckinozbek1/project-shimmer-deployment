"""Proofs of the producer's training pass (D-S57 item 3), on fixtures only.

    py -3.12 -X utf8 tools/producer_training_checks.py

No real model and no network. The pass runs on a tiny random Llama on the CPU with a stand-in for
peft (the head left trainable) and a character tokenizer with a chat template, so what is proved is
the file's checks, 168's encoding (prompt masked, one end-of-turn token in the answer), the
schedule, the loop, the saved identities, the hand-over to the test with the resident 168 and the
candidate on the base with its adapter, and bare_model's final-mode base with a declared adapter;
not 4-bit training, which only the first real run can show. Each refusal and three neutralisations
fail where they should. Exit 1 on any failure.
"""
import json
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "benchmark" / "baselines"), str(ROOT / "scripts"), str(ROOT / "tools")]
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
PASSED, FAILED = [], []
EOS = 1


def proof(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    (PASSED if ok else FAILED).append(name)


def raises(fn, text=""):
    try:
        fn()
    except (ValueError, RuntimeError) as exc:
        return text in str(exc)
    return False


class Tok:
    """Characters as tokens 3 to 92, one end-of-turn token (1), and a chat template that writes
    `role:` before each turn and the end-of-turn token after it."""
    eos_token_id = EOS

    def _ids(self, text):
        return [3 + (ord(c) % 90) for c in text]

    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=False):
        ids = []
        for m in messages:
            ids += self._ids(m["role"] + ":") + self._ids(m["content"]) + [EOS]
        if add_generation_prompt:
            ids += self._ids("assistant:")
        return ids


def tiny_load(torch, saved):
    from transformers import LlamaConfig, LlamaForCausalLM

    class Stand(torch.nn.Module):
        def __init__(self):
            super().__init__()
            torch.manual_seed(7)
            self.inner = LlamaForCausalLM(LlamaConfig(vocab_size=96, hidden_size=16, intermediate_size=32, num_hidden_layers=1,
                                                      num_attention_heads=2, num_key_value_heads=2, attn_implementation="eager"))
            for name, p in self.inner.named_parameters():
                p.requires_grad = name.startswith("lm_head")

        @property
        def config(self):
            return self.inner.config

        @property
        def device(self):
            return torch.device("cpu")

        def forward(self, **kw):
            return self.inner(**kw)

        def save_pretrained(self, directory, safe_serialization=True):
            saved.append(directory)
            Path(directory, "adapter_model.safetensors").write_bytes(self.inner.lm_head.weight.detach().numpy().tobytes())
            Path(directory, "adapter_config.json").write_text("{}", encoding="utf-8")
    return lambda training: (Tok(), Stand(), torch)


def replay_file(pairs, prefix):
    import hashlib
    prompts = []
    for i in range(pairs):
        text = "<prompt %s %d>" % (prefix, i)
        for checkpoint in ("tuned", "candidate"):
            prompts.append({"prompt_id": "p%04d" % (len(prompts) + 1), "set": prefix, "source_call_id": "%s%d" % (prefix, i),
                            "agent": "PROCESSOR", "backend": "local_producer", "checkpoint": checkpoint, "pair_of": "%s%d" % (prefix, i),
                            "doc_id": "d", "max_new_tokens": 8, "prompt_sha256": hashlib.sha256(text.encode()).hexdigest(),
                            "reference_reply_sha256": None, "prompt": text})
    return json.dumps({"schema": "b3-replay-prompts-v1", "prompt_count": len(prompts), "prompts": prompts}) + "\n"


def fixture(p, rows=24):
    out = []
    for i in range(rows):
        out.append({"row_id": "r%02d" % i, "system": "S", "user": "u%02d %s" % (i, "same" if i % 2 else "other"),
                    "answer": '{"items":[]}' if i % 2 else '{"items":[1]}', "family": "fixture", "share_alike": False})
    test, roles = replay_file(3, "test"), replay_file(2, "roles")
    value = {"schema": p.SCHEMA, "training": dict(p.RECIPE, model_id="m", revision="r", max_train_seconds=1000.),
             "publication": p.PUBLICATION, "data_manifest": {"fixture": True}, "rows": out, "rows_sha256": p._sha(p._canonical(out)),
             "test_text": test, "test_sha256": p._sha(test), "roles_text": roles, "roles_sha256": p._sha(roles)}
    value["recipe_sha256"] = p.recipe_digest(value)
    return value


def reseal(p, value):
    value["rows_sha256"] = p._sha(p._canonical(value["rows"]))
    value["test_sha256"], value["roles_sha256"] = p._sha(value["test_text"]), p._sha(value["roles_text"])
    value["recipe_sha256"] = p.recipe_digest(value)
    return value


def file_checks():
    import producer_train as p
    import replay_prompts
    value = fixture(p)
    proof("a whole file passes", p.check(value) is value)
    for label, change, text in (
            ("a changed row under the old digest", lambda v: v["rows"][0].update(user="x"), "not the declared ones"),
            ("a share-alike row", lambda v: (v["rows"][0].update(share_alike=True), reseal(p, v)), "share-alike"),
            ("a row with an unparseable answer", lambda v: (v["rows"][0].update(answer="{"), reseal(p, v)), "Expecting"),
            ("a recipe other than 168's", lambda v: (v["training"].update(learning_rate=.05), reseal(p, v)), "168's"),
            ("no training time", lambda v: (v["training"].update(max_train_seconds=0), reseal(p, v)), "training time"),
            ("a test row with no pair", lambda v: (v.update(test_text=replay_file(1, "test").replace('"pair_of": "test0"', '"pair_of": ""', 1)),
                                                   reseal(p, v)), "pair"),
            ("a test prompt asked of the candidate only", lambda v: (v.update(test_text=replay_file(1, "test").replace('"checkpoint": "tuned"', '"checkpoint": "candidate"')),
                                                                    reseal(p, v)), "once of tuned"),
            ("changed test bytes under the old digest", lambda v: v.update(test_text=v["test_text"] + " "), "declared bytes"),
            ("a training payload inside a test prompt", lambda v: (v["rows"][0].update(user="<prompt test 1>"), reseal(p, v)), "inside a test prompt"),
            ("a changed seed under the old recipe digest", lambda v: v["training"].update(seed=8), "168's")):
        broken = json.loads(json.dumps(value))
        change(broken)
        proof("refused: " + label, raises(lambda: p.check(broken), text))
    with tempfile.TemporaryDirectory() as folder:
        sealed = Path(folder) / "f.json"
        sealed.write_text(json.dumps(value), encoding="utf-8")
        proof("the sealed count is the test file's rows", len(p.load_prompts(sealed)) == 6)
        proof("replay_prompts hands the file to producer_train", replay_prompts.is_producer_training(sealed)
              and len(replay_prompts.load_prompts(sealed)) == 6 and not replay_prompts.is_judge_training(sealed))
    # Neutralised: the overlap refusal removed lets a test item be trained on.
    real = p._test_value
    leaked = json.loads(json.dumps(value))
    leaked["rows"][0]["user"] = "<prompt test 1>"
    reseal(p, leaked)
    p._test_value = lambda text, name: {"prompts": []}
    try:
        neutral = not raises(lambda: p.check(leaked), "inside a test prompt")
    finally:
        p._test_value = real
    proof("neutralised: with no test prompts read, the overlap is not refused", neutral)


def encoding_checks():
    import producer_train as p
    tok = Tok()
    row = {"row_id": "r", "system": "S", "user": "u", "answer": '{"a":1}'}
    e = p.encode(tok, row)
    proof("the prompt is masked and the answer is not", e["labels"][:e["prompt_length"]] == [-100] * e["prompt_length"]
          and all(v != -100 for v in e["labels"][e["prompt_length"]:]))
    proof("the answer ends on one end-of-turn token", e["labels"][-1] == EOS and e["labels"].count(EOS) == 1)
    proof("the prompt is the generation prompt the run sends",
          e["input_ids"][:e["prompt_length"]] == tok.apply_chat_template([{"role": "system", "content": "S"}, {"role": "user", "content": "u"}],
                                                                        tokenize=True, add_generation_prompt=True))

    class Twice(Tok):
        def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=False):
            ids = super().apply_chat_template(messages, tokenize, add_generation_prompt)
            return ids + [EOS] if messages[-1]["role"] == "assistant" else ids
    proof("refused: an answer with two end-of-turn tokens", raises(lambda: p.encode(Twice(), row), "exactly one"))
    value = fixture(p, rows=10)
    groups = p.schedule(value["rows"], value["training"])
    proof("two passes, each row once a pass, in groups of four", len(groups) == 6 and [len(g) for _, g in groups] == [4, 4, 2, 4, 4, 2]
          and sorted(r["row_id"] for e, g in groups if e == 1 for r in g) == sorted(r["row_id"] for r in value["rows"]))
    proof("each pass has its own order", [r["row_id"] for _, g in groups[:3] for r in g] != [r["row_id"] for _, g in groups[3:] for r in g])
    proof("the order is the seed's", p.schedule(value["rows"], value["training"]) == groups)


def training_checks():
    import torch
    import producer_train as p
    value = fixture(p)
    with tempfile.TemporaryDirectory() as folder:
        sealed = Path(folder) / "f.json"
        sealed.write_text(json.dumps(value), encoding="utf-8")
        calls = []

        def replay(path, out, paths, decision, max_new_tokens, reader):
            calls.append((Path(path).read_text(encoding="utf-8"), Path(out), list(paths), reader))
            return {"prompts": 0, "failures": {}}

        def readers(adapter):
            return {"tuned": {"adapter": None}, "candidate": {"adapter": adapter}}
        p.run(sealed, Path(folder) / "run", load=tiny_load(torch, []), replay=replay, readers=readers)
        out = Path(folder) / "run" / "training"
        result = json.loads((out / "result.json").read_text(encoding="utf-8"))
        proof("two passes over the rows", result["updates"] == 12 and result["planned_updates"] == 12)
        proof("candidate_half at half the schedule and candidate at its end",
              [(a["group"], a["update"]) for a in result["adapters"]] == [("candidate_half", 6), ("candidate", 12)])
        proof("the two adapters differ", result["adapters"][0]["weights_sha256"] != result["adapters"][1]["weights_sha256"])
        proof("an identity is the file's digest", p._sha((Path(result["adapters"][1]["path"]) / "adapter_model.safetensors").read_bytes())
              == result["adapters"][1]["weights_sha256"])
        proof("the loss falls", result["last_loss"] < result["first_loss"])
        proof("each update is logged", len((out / "losses.jsonl").read_text(encoding="utf-8").splitlines()) == 12)
        proof("the evidence is on disk", all((out / n).is_file() for n in ("config.json", "preflight.json", "losses.jsonl", "result.json", "progress.json")))
        proof("the test runs into D on the sealed paths, the roles into D/passes/roles on sdpa",
              [(c[1], c[2]) for c in calls] == [(Path(folder) / "run", ["sdpa", "sdpa_constrained"]),
                                                 (Path(folder) / "run" / "passes" / "roles", ["sdpa"])])
        proof("each runs the sealed bytes", [c[0] for c in calls] == [value["test_text"], value["roles_text"]])
        proof("the candidate reads the full adapter and 168 none", all(c[3]["tuned"]["adapter"] is None
              and c[3]["candidate"]["adapter"]["weights_sha256"] == result["adapters"][1]["weights_sha256"] for c in calls))
        proof("the half adapter is never handed to the test", all(c[3]["candidate"]["adapter"]["weights_sha256"] != result["adapters"][0]["weights_sha256"] for c in calls))
        proof("a measured rate cuts the schedule", p.plan_after_measure(1000, [10.] * 20, 3000., 200.) == 300)
        state = json.loads((out / "progress.json").read_text(encoding="utf-8"))
        proof("the progress file is one the progress reader reads (the roles part, its total and folder)",
              state["phase"] == "questions" and state["part"] == "roles" and state["questions_total"] == 4
              and state["records_under"].endswith("roles") and isinstance(state["started_epoch"], float))
        # Neutralised: the prompt left unmasked, the loss trains on the prompt too.
        real = p.encode

        def unmasked(tok, row):
            e = real(tok, row)
            return dict(e, labels=list(e["input_ids"]))
        p.encode = unmasked
        try:
            flat = p.train(fixture(p), Path(folder) / "flat", load=tiny_load(torch, []))
        finally:
            p.encode = real
        proof("neutralised: an unmasked prompt changes what is learned", flat["first_loss"] != result["first_loss"])


def reader_checks():
    """bare_model.LocalBackend in final mode: the base with a declared adapter, held to its
    digests by apply_adapter; the tuned producer refuses one. Stand-ins for the loaders."""
    import bare_model
    seen = {}
    saved = (bare_model.final_models.specification, bare_model.load_base_checkpoint, bare_model.apply_adapter,
             bare_model.checkpoint_record)
    bare_model.final_models.specification = lambda role, root=None: {"model_id": "m", "revision": "r"}
    bare_model.checkpoint_record = lambda checkpoint, spec: ({"checkpoint": checkpoint}, "r:w")
    bare_model.load_base_checkpoint = lambda spec=None, libs=None: ("tok", "base-model")
    bare_model.apply_adapter = lambda model, adapter, root=bare_model.ROOT: seen.setdefault("applied", (model, adapter)) and "wrapped"
    try:
        adapter = {"path": "a", "weights_sha256": "w" * 64, "config_sha256": "c" * 64}
        reader = {"model_mode": "final", "backend": "local_producer", "checkpoint": "base", "adapter": adapter,
                  "model_id": "m", "decoding": {"kwargs": {}}}
        backend = bare_model.LocalBackend(reader, None)
        loaded = backend.prepare()
        proof("final mode puts a declared adapter on the base", seen.get("applied") == ("base-model", adapter) and backend._mdl == "wrapped"
              and loaded["digest"].endswith("+adapter:" + "w" * 64) and loaded["checkpoint"]["adapter_applied"] is True)
        plain = bare_model.LocalBackend(dict(reader, adapter=None), None)
        proof("the base alone stays the base", plain.prepare()["digest"] == "r:w" and plain._mdl == "base-model")
        tuned = bare_model.LocalBackend(dict(reader, checkpoint="tuned"), None)
        proof("refused: a declared adapter on the tuned producer", _setup_error(lambda: tuned.prepare(), bare_model))
    finally:
        (bare_model.final_models.specification, bare_model.load_base_checkpoint, bare_model.apply_adapter,
         bare_model.checkpoint_record) = saved


def _setup_error(fn, bare_model):
    try:
        fn()
    except bare_model.SetupError as exc:
        return "its own adapter" in str(exc)
    return False


def roles_names_checks():
    import replay_prompts
    proof("refused: extract names a checkpoint bare_model does not load", raises(lambda: replay_prompts._checkpoint_names(["candidate"]), "each checkpoint once"))
    proof("a caller's own readers name the candidate", replay_prompts._checkpoint_names(["tuned", "candidate"], {"tuned": {}, "candidate": {}}) == ["tuned", "candidate"])


def pairing_checks():
    """producer_train.paired and test_files: each plain prompt asked of tuned and candidate,
    adjacent; the roles file's base rows asked of the candidate; a non-compact prompt refused."""
    import producer_train as p
    import hashlib
    plain = [{"prompt_id": "p0001", "set": "dev", "source_call_id": "e1", "prompt": "x",
              "prompt_sha256": hashlib.sha256(b"x").hexdigest(), "reference_reply_sha256": "r"}]
    out = p.paired(plain)
    proof("a plain prompt is asked of tuned then the candidate", [(r["checkpoint"], r["pair_of"], r["reference_reply_sha256"]) for r in out["prompts"]]
          == [("tuned", "dev:e1", "r"), ("candidate", "dev:e1", "r")] and out["prompt_count"] == 2)
    roles = [{"prompt_id": "p0001", "checkpoint": "tuned", "pair_of": "c1", "prompt": "y"}, {"prompt_id": "p0002", "checkpoint": "base", "pair_of": "c1", "prompt": "y"}]
    renamed = p.paired(roles, rename={"base": "candidate"})
    proof("the roles file's base row is asked of the candidate", [r["checkpoint"] for r in renamed["prompts"]] == ["tuned", "candidate"])
    import replay_prompts
    with tempfile.TemporaryDirectory() as folder:
        bad = Path(folder) / "bad.json"
        bad.write_text(replay_file(1, "x"), encoding="utf-8")
        proof("refused: a non-compact prompt in the compact test", raises(lambda: p.test_files([bad], bad, Path(folder) / "t", Path(folder) / "r"), "compact producer prompts only"))
    # Neutralised: a pairing that drops the candidate row is refused by the file check.
    real = p.TEST_CHECKPOINTS
    p.TEST_CHECKPOINTS = ("tuned",)
    try:
        lone = p.paired(plain)
    finally:
        p.TEST_CHECKPOINTS = real
    proof("neutralised: a test asked of tuned alone is refused", raises(lambda: p._test_value(json.dumps(lone), "test"), "once of tuned"))
    _ = replay_prompts


def author_checks():
    """tuning/producer_v4/author.py's pure parts on a planted carrier: windows of three sentences,
    no carrier with an id or the context marker, v3's clauses placed between the sentences, the
    frozen interpreter's label through the validator's own form, an overlap dropped. Runs last: it
    installs v3's local-only guard in this process."""
    sys.path.insert(0, str(ROOT / "tuning" / "producer_v4"))
    # The tuning modules import plain names (`common`, `author`, `runtime`) that other modules of
    # this process already took; the v4 author is imported with its own.
    for name in ("common", "author", "runtime", "local_common", "structural"):
        sys.modules.pop(name, None)
    import author as a
    sentences = ["The agency reviewed its annual plans in detail during the period and compared them with earlier years.",
                 "Officials met with several groups to discuss the program's goals, its staffing and its long-term direction.",
                 "The review covered spending across the regional offices and the central office over the same years.",
                 "A further summary followed in the closing part of the document for readers."]
    doc = {"doc_id": "d", "paragraphs": [" ".join(sentences)]}
    found = a.windows(doc)
    proof("a window is three consecutive sentences", found == [sentences[:3]])
    proof("a carrier naming an id is never a window", a.windows({"doc_id": "d", "paragraphs": [" ".join(sentences[:2] + ["CLM-X was cited (REF-0001) there today."])]}) == [])
    proof("the planted carrier states nothing to the frozen interpreter", a.reading(" ".join(sentences[:3])) == "none")
    body = a.plan(7, sentences[:3])
    proof("v3's clauses sit between the carrier's sentences", all(s in body for s in sentences[:3]) and len(body) > 3
          and any(g in body for g in a.v3.GAPS))
    row = a.row_of(7, "fixture", "d", sentences[:3])
    proof("a row is labelled by the frozen interpreter and written in 168's form",
          row is not None and json.loads(row["answer"]).get("items") is not None and row["system"].startswith("Return only one JSON object"))
    proof("a carrier sharing an 8-word run with a test prompt is dropped",
          bool(a.word_runs(" ".join(sentences[:3])) & a.word_runs("x " + sentences[1] + " y")))
    proof("dashes are rewritten", "\u2014" not in a.clean("one\u2014two") and "\u2013" not in a.clean("1\u20132"))


def split_checks():
    """tuning/producer_v4/split_heldout.halves: by document, no document on both sides, seeded."""
    sys.path.insert(0, str(ROOT / "tuning" / "producer_v4"))
    import split_heldout as s
    rows = [{"id": "r%d" % i, "doc": "d%d" % (i // 3), "src": "a" if i < 12 else "b"} for i in range(24)]
    tune, held = s.halves(rows, lambda r: r["doc"], lambda r: r["src"])
    docs_t, docs_h = {r["doc"] for r in tune}, {r["doc"] for r in held}
    proof("the split is by document: no document on both sides", not (docs_t & docs_h) and len(tune) + len(held) == 24)
    proof("each stratum is halved by documents", sum(r["src"] == "a" for r in tune) == 6 and sum(r["src"] == "b" for r in tune) == 6)
    proof("the split is the seed's", s.halves(rows, lambda r: r["doc"], lambda r: r["src"]) == (tune, held))
    t2, h2 = s.halves(rows, lambda r: r["id"], lambda r: r["src"])
    proof("neutralised: split by row, a document lands on both sides", bool({r["doc"] for r in t2} & {r["doc"] for r in h2}))


def _measurement(folder, rows_spec):
    """A prompts file and its measurement: rows_spec is [(set, pair, {checkpoint: (valid_sdpa, valid_constrained, right)})]."""
    prompts, rows = [], []
    for set_name, pair, by in rows_spec:
        for checkpoint, (v_sdpa, v_con, right) in by.items():
            pid = "p%04d" % (len(prompts) + 1)
            prompts.append({"prompt_id": pid, "set": set_name, "pair_of": pair, "checkpoint": checkpoint})
            rows.append({"prompt_id": pid, "sdpa": {"contract": {"valid": v_sdpa}}, "sdpa_constrained": {"contract": {"valid": v_con},
                         "reference_identical": right}})
    pp, mp = Path(folder) / "prompts.json", Path(folder) / "m.json"
    pp.write_text(json.dumps({"prompts": prompts}), encoding="utf-8")
    mp.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    return pp, mp


def score_checks():
    import producer_score as sc
    proof("the sign test: 5 wins and no loss is .031, 7 and none .0078", abs(sc.sign_p(5, 0) - 0.03125) < 1e-12 and abs(sc.sign_p(7, 0) - 0.0078125) < 1e-12)
    proof("the smallest passing counts at k=1 (.025) start at 6 wins and no loss",
          sc.smallest_passes(sc.heldout_alpha(1))[:3] == [(6, 0), (8, 1), (10, 2)])
    proof("the tuning test's smallest passing counts start at 7 and none", sc.smallest_passes(sc.TUNING_ALPHA)[0] == (7, 0))
    with tempfile.TemporaryDirectory() as folder:
        spec = [("dev", "e%d" % i, {"tuned": (True, i > 0, True), "candidate": (True, i > 0, True)}) for i in range(4)]
        spec += [("partitions_tune", "q%d" % i, {"tuned": (False, True, False), "candidate": (True, True, False)}) for i in range(7)]
        spec += [("fresh_tune", "f%d" % i, {"tuned": (True, True, False), "candidate": (True, True, i < 2)}) for i in range(5)]
        pp, mp = _measurement(folder, spec)
        roles = Path(folder) / "roles.json"
        roles.write_text(json.dumps({"pairs": {"sdpa": {"archivist": {"checkpoints": ["tuned", "candidate"], "a_only_valid": 1, "b_only_valid": 0}}}}), encoding="utf-8")
        record = sc.tuning(1, pp, mp, roles, roles)
        proof("a tuning record passes on 7 partitions won and none lost, with the DEV invalid rows the same",
              record["passed"] and record["b_partitions_tune"]["candidate_only"] == 7 and record["a_no_dev_loss"]["same_rows"]
              and record["real_progress"])
        spec2 = [(s_, p_, dict(by, candidate=(by["candidate"][0], True, by["candidate"][2])) if s_ == "dev" else by) for s_, p_, by in spec]
        pp2, mp2 = _measurement(folder, spec2)
        proof("refused: a candidate that turns a DEV refusal valid fails (a)", not sc.tuning(1, pp2, mp2, roles, roles)["passed"])
        worse = Path(folder) / "worse.json"
        worse.write_text(json.dumps({"pairs": {"sdpa": {"archivist": {"checkpoints": ["tuned", "candidate"], "a_only_valid": 8, "b_only_valid": 0}}}}), encoding="utf-8")
        proof("refused: a role on which 168 is better fails (d)", not sc.tuning(1, pp, mp, roles, worse)["passed"])
        prev = Path(folder) / "prev.json"
        prev.write_text(json.dumps(record), encoding="utf-8")
        proof("no real progress when nothing gains 3 over the previous attempt", sc.tuning(2, pp, mp, roles, roles, prev)["real_progress"] is False)


def gate_checks():
    import producer_score as sc
    import base64
    with tempfile.TemporaryDirectory() as folder:
        held = Path(folder) / "heldout.json"
        held.write_text("held", encoding="utf-8")
        digest = sc._sha(held.read_bytes())
        line = "| %s | 1 | 0.025 | 1 | heldout.json %s | abc1234 | 2026-11-09 | |" % (sc.PART, digest)
        head = "| Part | k | Alpha | Attempt | Held-out material (file, digest) | Tuning pass record (commit) | Written | Result |\n|---|---|---|---|---|---|---|---|\n"
        passed = json.dumps({"part": sc.PART, "attempt": 1, "passed": True})

        def show(lines, record=passed):
            def inner(commit, path, root=None):
                if path == sc.OPENINGS:
                    return "# x\n\n" + head + lines + "\n"
                if path.endswith("attempt_1_tuning.json") and commit == "abc1234":
                    return record
                raise ValueError("not committed: " + path)
            return inner
        proof("the gate opens on a committed line and a committed passing tuning record", sc.gate(1, [held], show=show(line)) == (1, 0.025))
        proof("refused: no committed line for the attempt", raises(lambda: sc.gate(1, [held], show=show("")), "no single line"))
        proof("refused: another attempt's line", raises(lambda: sc.gate(2, [held], show=show(line)), "no single line"))
        proof("refused: a tuning record that did not pass", raises(lambda: sc.gate(1, [held], show=show(line, json.dumps({"part": sc.PART, "attempt": 1, "passed": False}))), "did not pass"))
        proof("refused: a line naming other held-out material", raises(lambda: sc.gate(1, [held], show=show(line.replace(digest, "0" * 64))), "digest"))
        proof("refused: k and alpha that disagree", raises(lambda: sc.gate(1, [held], show=show(line.replace("| 0.025 |", "| 0.05 |"))), "0.05 / 2^k"))
        pp, mp = _measurement(folder, [("fresh_heldout", "h%d" % i, {"tuned": (True, True, False), "candidate": (True, True, True)}) for i in range(6)])
        result = sc.heldout_score(1, pp, mp, [held], show=show(line))
        proof("a held-out score is pass or fail with counts and names no item", result["passed"] and result["c"]["candidate_only"] == 6
              and "h0" not in json.dumps(result) and result["alpha"] == 0.025)
        proof("refused: a held-out score with no committed opening", raises(lambda: sc.heldout_score(1, pp, mp, [held], show=show("")), "no single line"))
        real = sc.gate
        sc.gate = lambda *a, **k: (1, 0.025)
        try:
            opened = not raises(lambda: sc.heldout_score(1, pp, mp, [held], show=show("")), "no single line")
        finally:
            sc.gate = real
        proof("neutralised: with the gate removed, a held-out part is scored with no opening", opened)
        adapter = Path(folder) / "adapter"
        adapter.mkdir()
        (adapter / "adapter_model.safetensors").write_bytes(b"weights")
        (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
        hp = Path(folder) / "hp.json"
        hp.write_text(replay_file(2, "fresh_heldout"), encoding="utf-8")
        out = Path(folder) / "heldout_file.json"
        proof("refused: a held-out file assembled with no committed opening",
              raises(lambda: sc.heldout_assemble(1, adapter, hp, [held], out, show=show("")), "no single line") and not out.exists())
        sc.heldout_assemble(1, adapter, hp, [held], out, show=show(line))
        import producer_train as p
        calls = []
        p.heldout_run(out, Path(folder) / "run", replay=lambda path, o, **kw: calls.append((Path(o), kw["reader"])) or {"prompts": 0},
                      readers=lambda a: {"tuned": {"adapter": None}, "candidate": {"adapter": a}})
        proof("the held-out pass writes the adapter held to its digest and asks it beside 168, with no training",
              calls and calls[0][1]["candidate"]["adapter"]["weights_sha256"] == sc._sha(b"weights")
              and (Path(folder) / "run" / "heldout" / "candidate" / "adapter_model.safetensors").read_bytes() == b"weights"
              and not (Path(folder) / "run" / "training").exists())
        bad = json.loads(out.read_text(encoding="utf-8"))
        bad["adapter"]["adapter_model.safetensors"]["base64"] = base64.b64encode(b"other").decode()
        proof("refused: a held-out file whose adapter is not its digest", raises(lambda: p.check_heldout(bad), "not its digest"))
        import replay_prompts
        proof("the replay pass hands the held-out file to its own runner and counts its rows",
              replay_prompts.is_producer_training(out) and len(replay_prompts.load_prompts(out)) == 4)


def main():
    split_checks()
    score_checks()
    gate_checks()
    file_checks()
    encoding_checks()
    training_checks()
    reader_checks()
    roles_names_checks()
    pairing_checks()
    author_checks()
    print("producer training checks: %d proofs passed%s" % (len(PASSED), ", FAILED %d" % len(FAILED) if FAILED else ", all passed"))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
