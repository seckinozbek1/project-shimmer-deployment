#!/usr/bin/env python3
"""Check 520 (lane/v-synlab-launch; Seckin 18 November 2026 14:20, D-706 item 1, NEG-SYNTH-A): role V's blind
labelling job rides the sealed replay pass, and its labels are read on the laptop from the fetched evidence.

Proofs, each run as built (passes), neutralised (must fail), restored and run again (passes):
- round_trip: tools/neg_synth_label.py build-pass renders every sheet position's question on the laptop into a
  `neg-synth-label-pass-v1` file that the sealer's own reader (replay_prompts.load_prompts) counts; the replay
  pass's own `main` hands it to neg_synth_label_pass.run (a fake model, a fake sealed cache), which leaves one reply
  record per prompt as the runner's replay_observation counts them; read-pass reads each set's labels from the
  collected evidence archive and they match the cards (kappa 1, nothing dropped). Neutralised: the replay
  dispatch no longer recognises the file;
- inputs_held: a sheets file whose SHA-256 is not the one role S handed over, or a sheet carrying an answer field,
  is refused before a question is written. Neutralised: the sheets check lets every sheet through;
- model_sealed_only: the labeller comes from the sealed cache alone: a candidate not sealed or not loadable by the
  pinned transformers is passed over and counted, other terms refuse, and a file declaring a Qwen candidate is
  refused. Neutralised: the model rule accepts any id;
- reply_held: a saved reply that differs from the digest its pass recorded refuses the read. Neutralised: the
  reader skips that comparison;
- counts_only: what build-pass, the pass and read-pass print holds no quote, item id or stance word.
  Neutralised: read-pass prints its labels.

No model, no network, no real item: the cards, builds and replies are tools/neg_synth_checks.py's invented
fixtures, in temporary folders outside the repository.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tools"), str(ROOT / "scripts"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_synth as ns  # noqa: E402
import neg_synth_checks as nsc  # noqa: E402
import neg_synth_label as nsl  # noqa: E402
import neg_synth_label_pass as lp  # noqa: E402
import replay_prompts  # noqa: E402

CFG = nsc.CFG
SETS = {"dev_1": nsc.SEEDS[:2], "pilot_1": nsc.SEEDS[2:]}
SEALED = {"sealed": True, "revision": "f" * 40, "terms": "apache-2.0", "loadable": True, "model_type": "olmo2"}


class Fixture:
    """Cards, builds and sheets files for two sets in a temporary folder."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.cards, self.builds, self.paths, self.expected = {}, {}, [], {}
        for name, seeds in SETS.items():
            cards = [nsc._card(s) for s in seeds]
            builds = [ns.assemble(c, nsc.fixture_reply(c), CFG) for c in cards]
            path = self.folder / ("sheets_%s.json" % name)
            path.write_text(json.dumps({"schema": ns.SHEET_SCHEMA, "sheets": [ns.label_sheet(b) for b in builds]},
                                       indent=1), encoding="utf-8")
            self.cards[name], self.builds[name] = cards, builds
            self.paths.append(path)
            self.expected[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def all_builds(self):
        return [b for bs in self.builds.values() for b in bs]


def fake_generate(builds, confidence=None):
    """A fake model: the oracle reply, and as its fields' decisions the true answer at `confidence(prompt)`
    (0.9 by default) with the rest shared out."""
    many = nsc._truthful(builds)

    def generate(prompt, answers):
        reply = many([prompt])[0]
        obj = json.loads(reply.split("```json" + chr(10), 1)[1].split(chr(10) + "```", 1)[0])
        top_p = confidence(prompt) if confidence else 0.9
        decisions = {}
        for field, values in answers.items():
            top = str(obj.get(field))
            rest = (1 - top_p) / (len(values) - 1)
            probs = {v: (top_p if v == top else rest) for v in values}
            decisions[field] = {"probabilities": probs, "top": top, "top_probability": top_p,
                                "declared_mass": 0.99, "step": 3}
        return {"reply": reply, "prompt_tokens": len(prompt.split()), "new_tokens": len(reply.split()),
                "decisions": decisions}
    return generate


def fake_info(table):
    return lambda repo: table.get(repo, {"sealed": False})


def run_pass(fx, prompts_path, evidence_root, generate=None):
    """replay_prompts.main on the file (as the runner's replay pass calls it), then the folder archived as the
    controller collects it. Returns (exit code, archive path, pass folder, stdout)."""
    out = Path(evidence_root) / "evidence" / "b1" / "label"
    first = CFG["labeller"]["candidates"][0]
    buf = io.StringIO()
    with patch.object(lp, "hf_generate", lambda *a: generate or fake_generate(fx.all_builds())), \
            patch.object(lp, "sealed_info", fake_info({first: SEALED})), contextlib.redirect_stdout(buf), \
            contextlib.redirect_stderr(io.StringIO()):
        code = replay_prompts.main(["run", "--prompts", str(prompts_path), "--out", str(out), "--paths", "sdpa"])
    archive = Path(evidence_root) / "collected_evidence.tar.gz"
    if out.is_dir():
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(Path(evidence_root) / "evidence", arcname="evidence")
    return code, archive, out, buf.getvalue()


def build(fx, out):
    return nsl.build_pass([str(p) for p in fx.paths], dict(fx.expected), out, CFG)


# ---------------------------------------------------------------------------


def observe_round_trip():
    import ordinary_final_run as runner
    with tempfile.TemporaryDirectory() as tmp:
        fx = Fixture(tmp)
        prompts_path = Path(tmp) / "work" / "label_pass_prompts.json"
        value = build(fx, prompts_path)
        counted = len(replay_prompts.load_prompts(prompts_path))
        code, archive, folder, _ = run_pass(fx, prompts_path, Path(tmp) / "run")
        seen = runner.replay_observation(folder, value["prompt_count"], ["sdpa"])
        out = {"exit": code, "sealer_count_equal": counted == value["prompt_count"],
               "one_record_a_prompt": seen["reply_records"] == seen["items"] and seen["summary_written"]}
        for name, path in zip(SETS, fx.paths):
            labels, record = nsl.read_pass(prompts_path, path, archive, CFG)
            cmp = ns.compare_labels(fx.cards[name], labels["labels"])
            out[name] = {"dropped": cmp["dropped_ids"], "perfect": cmp["mapping"]["kappa"] == 1.0,
                         "unread": sum(v for k, v in record["by_reason"].items() if k != "read"),
                         "model": record["model_id"]}
        return out


def expected_round_trip():
    first = CFG["labeller"]["candidates"][0]
    one = {"dropped": [], "perfect": True, "unread": 0, "model": first}
    return {"exit": 0, "sealer_count_equal": True, "one_record_a_prompt": True, "dev_1": one, "pilot_1": one}


def neutralise_round_trip():
    return patch.object(replay_prompts, "is_neg_synth_label", lambda path: False)


def _attempt(fn):
    try:
        fn()
        return "built"
    except ValueError:
        return "refused"


def observe_inputs_held():
    with tempfile.TemporaryDirectory() as tmp:
        fx = Fixture(tmp)
        wrong = dict(fx.expected, dev_1="0" * 64)
        leaky_dir = Path(tmp) / "leaky"
        leaky_dir.mkdir()
        leaky = leaky_dir / fx.paths[0].name
        value = json.loads(fx.paths[0].read_text(encoding="utf-8"))
        value["sheets"][0]["positions"][0]["stance"] = "oppose"
        leaky.write_text(json.dumps(value), encoding="utf-8")
        leaky_expected = dict(fx.expected, dev_1=hashlib.sha256(leaky.read_bytes()).hexdigest())
        out_path = Path(tmp) / "work" / "p.json"
        return {"clean": _attempt(lambda: build(fx, out_path)),
                "wrong_digest": _attempt(lambda: nsl.build_pass([str(p) for p in fx.paths], wrong, out_path, CFG)),
                "answer_field": _attempt(lambda: nsl.build_pass([str(leaky), str(fx.paths[1])], leaky_expected,
                                                                out_path, CFG)),
                "inside_repository": _attempt(lambda: build(fx, ROOT / "output" / "never_written.json"))}


def expected_inputs_held():
    return {"clean": "built", "wrong_digest": "refused", "answer_field": "refused", "inside_repository": "refused"}


def neutralise_inputs_held():
    return patch.object(nsl, "check_sheets", lambda value: value["sheets"])


def observe_model_sealed_only():
    with tempfile.TemporaryDirectory() as tmp:
        fx = Fixture(tmp)
        path = Path(tmp) / "work" / "p.json"
        value = build(fx, path)
        first, second = CFG["labeller"]["candidates"][:2]

        def resolved(table):
            try:
                r = lp.resolve(value, fake_info(table))
                return r["model_id"], r["passed_over"]
            except ValueError:
                return "refused"

        qwen = copy.deepcopy(value)
        qwen["labeller"]["candidates"] = ["Qwen/Qwen2.5-7B-Instruct"] + qwen["labeller"]["candidates"]
        dated = copy.deepcopy(value)
        dated["labeller"]["candidates"] = ["allenai/olmo-instruct-20261101"]
        return {"first": resolved({first: SEALED, second: SEALED}),
                "not_sealed": resolved({second: SEALED}),
                "not_loadable": resolved({first: dict(SEALED, loadable=False), second: SEALED}),
                "other_terms": resolved({c: dict(SEALED, terms="other") for c in (first, second)}),
                "qwen_file": _attempt(lambda: lp.check_file(qwen)),
                "dated_file": _attempt(lambda: lp.check_file(dated))}


def expected_model_sealed_only():
    first, second = CFG["labeller"]["candidates"][:2]
    return {"first": (first, {}), "not_sealed": (second, {first: "not_sealed"}),
            "not_loadable": (second, {first: "not_loadable"}), "other_terms": "refused",
            "qwen_file": "refused", "dated_file": "refused"}


def neutralise_model_sealed_only():
    return patch.object(lp, "check_model", lambda model_id, labeller, generator_family: model_id)


def observe_reply_held():
    with tempfile.TemporaryDirectory() as tmp:
        fx = Fixture(tmp)
        prompts_path = Path(tmp) / "work" / "p.json"
        build(fx, prompts_path)
        _code, _archive, folder, _ = run_pass(fx, prompts_path, Path(tmp) / "run")
        out = {"clean": _attempt(lambda: nsl.read_pass(prompts_path, fx.paths[0], folder.parents[2], CFG))}
        record = sorted((folder / "audit" / "model_replies").glob("*.json"))[0]
        value = json.loads(record.read_text(encoding="utf-8"))
        value["reply"]["text"] = value["reply"]["text"].replace("support", "oppose").replace("accept", "reject") + " "
        record.write_text(json.dumps(value), encoding="utf-8")
        out["tampered"] = _attempt(lambda: nsl.read_pass(prompts_path, fx.paths[0], folder.parents[2], CFG))
        return out


def expected_reply_held():
    return {"clean": "built", "tampered": "refused"}


def neutralise_reply_held():
    return patch.object(nsl, "pass_replies", _lenient_pass_replies)


def _lenient_pass_replies(evidence, prompts_path):
    """pass_replies without the digest comparisons (the neutralised reader)."""
    found = [(n, json.loads(evidence.read(n))) for n in evidence.names if n.endswith("/" + lp.MEASUREMENT_FILE)]
    name, m = [(n, v) for n, v in found if isinstance(v, dict) and v.get("schema") == lp.MEASUREMENT_SCHEMA][0]
    folder = name[: -len(lp.MEASUREMENT_FILE)] + "audit/model_replies/"
    replies, decisions = {}, {}
    for rec_name in sorted(n for n in evidence.names if n.startswith(folder) and n.endswith(".json")):
        r = json.loads(evidence.read(rec_name))
        replies[r["doc_id"]] = r["reply"]["text"]
        decisions[r["doc_id"]] = (r.get("decision") or {}).get("fields") or {}
    return m, replies, decisions


def observe_counts_only():
    with tempfile.TemporaryDirectory() as tmp:
        fx = Fixture(tmp)
        prompts_path = Path(tmp) / "work" / "p.json"
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            nsl.main(["build-pass"] + sum((["--sheets", str(p)] for p in fx.paths), [])
                     + sum((["--expect", "%s=%s" % kv] for kv in fx.expected.items()), []) + ["--out", str(prompts_path)])
        _code, archive, _folder, pass_out = run_pass(fx, prompts_path, Path(tmp) / "run")
        printed.write(pass_out)
        with contextlib.redirect_stdout(printed):
            nsl.main(["read-pass", "--prompts", str(prompts_path), "--sheets", str(fx.paths[0]), "--evidence",
                      str(archive), "--out", str(Path(tmp) / "work" / "labels_dev_1.json"), "--record",
                      str(Path(tmp) / "work" / "LABELLER_dev_1.json")])
        text = printed.getvalue()
        quotes = [p["quote"] for b in fx.all_builds() for p in b["positions"]]
        items = [b["item_id"] for b in fx.all_builds()]
        stances = sorted(set(nsl.load_template(CFG)["stances"]))
        return {"quote": any(q in text for q in quotes), "item_id": any(i in text for i in items),
                "stance_word": any('"%s"' % s in text for s in stances), "printed": bool(text.strip())}


def expected_counts_only():
    return {"quote": False, "item_id": False, "stance_word": False, "printed": True}


def neutralise_counts_only():
    real = nsl.read_pass

    def loud(*a, **k):
        labels, record = real(*a, **k)
        print(json.dumps(labels))
        return labels, record
    return patch.object(nsl, "read_pass", loud)


def observe_model_preflight():
    """The lead 18:39: the labeller is checked once it loads, before its first prompt. The pinned transformers
    resolves the declared model type to the declared class (its own mapping, read here); a model of that class with
    a tokenizer whose built-in template and end-of-text token are the declared ones passes; another class, a
    template without a marker, another end-of-text token or an undeclared labeller is refused."""
    from transformers.models.auto.modeling_auto import MODEL_FOR_CAUSAL_LM_MAPPING_NAMES
    import transformers
    declared = json.loads(lp.PREFLIGHT_FILE.read_text(encoding="utf-8"))
    repo = "allenai/OLMo-2-1124-7B-Instruct"
    want = declared["models"][repo]
    olmo2 = type(want["model_class"], (), {})
    other = type("LlamaForCausalLM", (), {})

    class Tok:
        def __init__(self, template, eos):
            self.chat_template, self.eos_token = template, eos
    good = Tok("{{ '<|user|>' }}{{ m }}{{ '<|assistant|>' }}", "<|endoftext|>")

    def attempt(fn):
        try:
            return fn() and "passed"
        except ValueError:
            return "refused"
    return {"pinned": transformers.__version__,
            "mapping": MODEL_FOR_CAUSAL_LM_MAPPING_NAMES.get(want["model_type"]) == want["model_class"],
            "good": attempt(lambda: lp.model_preflight(repo, olmo2(), good, declared)),
            "other_class": attempt(lambda: lp.model_preflight(repo, other(), good, declared)),
            "no_assistant": attempt(lambda: lp.model_preflight(repo, olmo2(), Tok("<|user|>", "<|endoftext|>"), declared)),
            "other_eos": attempt(lambda: lp.model_preflight(repo, olmo2(), Tok(good.chat_template, "</s>"), declared)),
            "undeclared": attempt(lambda: lp.model_preflight("x/y", olmo2(), good, declared))}


def expected_model_preflight():
    return {"pinned": "4.51.3", "mapping": True, "good": "passed", "other_class": "refused", "no_assistant": "refused",
            "other_eos": "refused", "undeclared": "refused"}


def neutralise_model_preflight():
    return patch.object(lp, "model_preflight", lambda model_id, model, tok, declared=None: {"model_class": "any"})


PROOFS = ("round_trip", "inputs_held", "model_sealed_only", "reply_held", "counts_only", "model_preflight")
GROUPS = {"520": PROOFS}


def _caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a neutralised proof may raise; that is its failure
        return "raised %s" % type(exc).__name__


def run_group(number="520"):
    done = []
    for name in GROUPS[number]:
        space = globals()
        observe, expected, neutralise = space["observe_" + name], space["expected_" + name], space["neutralise_" + name]
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                first = observe()
                with neutralise():
                    broken = _caught(observe)
                again = observe()
        except Exception as exc:
            return "FAIL", "%s: %s %s" % (name, type(exc).__name__, str(exc)[:300])
        if first != expected():
            return "FAIL", "%s as built: %s" % (name, str(first)[:600])
        if broken == expected():
            return "FAIL", "%s still passes when neutralised" % name
        if again != expected():
            return "FAIL", "%s after restore: %s" % (name, str(again)[:400])
        done.append(name)
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, no model: role V's labelling pass on the "
                    "sealed replay pass, labels read from the fetched evidence (%s)" % (len(done), ", ".join(done)))


if __name__ == "__main__":
    status, detail = run_group(sys.argv[1] if len(sys.argv) > 1 else "520")
    print(status, detail)
    raise SystemExit(0 if status == "PASS" else 1)
