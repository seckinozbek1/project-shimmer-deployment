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
- wording_* (lane/label-wording-reader): the wording field read by form against the chosen article's own
  bracketed wordings: an identical quote read as its number (neutralised: no quote counted), two identical
  wordings or a number and a quote that disagree refused quote_ambiguous (neutralised: the first taken), an
  overlapping quote refused quote_not_exact (neutralised: no overlap seen), a number in one matched pair of marks
  read (neutralised: bare digits only), a number above the chosen article's own count refused
  number_above_article (neutralised: counted as not_declared);
- reread_quotes: read-pass on a pass whose model quoted its wordings reads every label, the cards' own.
  Neutralised: the reader before the lane; reread_new_names: read-pass refuses an output that exists and writes a
  second reading under new names. Neutralised: the existing-output refusal skipped.
- D-799 (lane/label-constrained; a tiny character tokenizer and a fake model run through the pass's own
  make_generate, LabelGrammar and DECODING-B's ContractProcessor): constraint_impossible, a model preferring a
  partial quote, a changed quote, free text or prose around the object is refused by the reader unconstrained, and
  under the constraint writes only an object inside the language that the reader reads, its interventions counted;
  twenty random-score models stay inside too (neutralised: the processor leaves the scores unmasked);
  per_article_count, the wording list is the decoded article's own count, for the constraint and the confidence
  record (neutralised: the sheet-wide list); old_file_read, a v1 prompts file with no constraint is still checked,
  run with the old two-argument generate and read again (neutralised: only v2 recognised); outside_counted, a
  reply still outside the language is counted by reason in the pass record and per set by read-pass, never read
  by guess (neutralised: every reply called inside).

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
from collections import Counter
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

    def generate(prompt, answers, constraint=None):
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


# ---------------------------------------------------------------------------
# lane/label-wording-reader (19 November 2026): the wording field read by form against the chosen article's own
# bracketed wordings. Invented articles only; each rule has its own proof and its own neutralisation.

T = nsl.load_template(CFG)
WORDING_SHEET = {"persona": {"id": "PX"}, "articles": [
    {"id": "A1", "text": "Alpha [beta gamma] delta [epsilon zeta] and [eta]."},
    {"id": "A2", "text": "Theta iota, no bracket."},
    {"id": "A3", "text": "[kappa] or [kappa] or [lambda]"},
    {"id": "A4", "text": "[2] or [mu]"}]}
WORDING_POSITION = {"party": "PY"}


def _wording(article, value):
    """The proposal read from one invented reply, or the reason it is refused."""
    reply = "Reading.\n```json\n" + json.dumps({"article": article, "wording": value, "stance": T["stances"][0]}) + "\n```"
    lab, why = nsl.read_answer(reply, WORDING_SHEET, WORDING_POSITION, T)
    return why if why else lab["proposal"]


def observe_wording_quote_exact():
    return {"first": _wording("A1", "beta gamma"), "second_bracketed": _wording("A1", "[epsilon zeta]"),
            "third_quoted_case": _wording("A1", '"Eta"'), "spaces": _wording("A1", "  beta   gamma "),
            "whole": _wording("A2", "Whole"), "bare_number": _wording("A1", "2")}


def expected_wording_quote_exact():
    return {"first": 1, "second_bracketed": 2, "third_quoted_case": 3, "spaces": 1, "whole": None, "bare_number": 2}


def neutralise_wording_quote_exact():
    return patch.object(nsl, "quoted_wordings", lambda k, span_keys: [])


def observe_wording_quote_ambiguous():
    return {"two_spans": _wording("A3", "kappa"), "one_of_three": _wording("A3", "lambda"),
            "number_and_quote_differ": _wording("A4", "2"), "number_and_quote_agree": _wording("A4", "mu")}


def expected_wording_quote_ambiguous():
    return {"two_spans": "wording:" + nsl.QUOTE_AMBIGUOUS, "one_of_three": 3,
            "number_and_quote_differ": "wording:" + nsl.QUOTE_AMBIGUOUS, "number_and_quote_agree": 2}


def neutralise_wording_quote_ambiguous():
    """Only the first identical wording counted, so two spans alike read as the first."""
    real = nsl.quoted_wordings
    return patch.object(nsl, "quoted_wordings", lambda k, span_keys: real(k, span_keys)[:1])


def observe_wording_quote_not_exact():
    return {"part": _wording("A1", "beta"), "more": _wording("A1", "beta gamma delta"),
            "unrelated": _wording("A1", "omega")}


def expected_wording_quote_not_exact():
    return {"part": "wording:" + nsl.QUOTE_NOT_EXACT, "more": "wording:" + nsl.QUOTE_NOT_EXACT,
            "unrelated": "wording:" + nsl.af.NOT_DECLARED}


def neutralise_wording_quote_not_exact():
    return patch.object(nsl, "overlaps", lambda k, span_keys: False)


def observe_wording_marked_number():
    return {"square": _wording("A1", "[2]"), "round": _wording("A1", "(3)"), "angle": _wording("A1", "<1>"),
            "integer": _wording("A1", 3), "unmatched": _wording("A1", "(2]"), "hash": _wording("A1", "#2")}


def expected_wording_marked_number():
    nd = "wording:" + nsl.af.NOT_DECLARED
    return {"square": 2, "round": 3, "angle": 1, "integer": 3, "unmatched": nd, "hash": nd}


def neutralise_wording_marked_number():
    return patch.object(nsl, "marked_number", lambda k: k if k.isdigit() else None)


def observe_wording_number_above_article():
    """The number is held to the chosen article's own count, never the sheet's largest (A2 has none, A1 three)."""
    return {"above_own": _wording("A1", "4"), "above_marked": _wording("A1", "[7]"),
            "article_without_brackets": _wording("A2", "1"), "own_last": _wording("A1", "3"),
            "zero": _wording("A1", "0")}


def expected_wording_number_above_article():
    return {"above_own": "wording:" + nsl.NUMBER_ABOVE_ARTICLE, "above_marked": "wording:" + nsl.NUMBER_ABOVE_ARTICLE,
            "article_without_brackets": "wording:" + nsl.NUMBER_ABOVE_ARTICLE, "own_last": 3,
            "zero": "wording:" + nsl.af.NOT_DECLARED}


def neutralise_wording_number_above_article():
    return patch.object(nsl, "NUMBER_ABOVE_ARTICLE", nsl.af.NOT_DECLARED)


def quoting_generate(builds):
    """The fake model writing each proposal as its bracketed wording's own text (every other proposal with the
    article's brackets around it) instead of its number; the article is the true one."""
    sheets = {b["item_id"]: ns.label_sheet(b) for b in builds}
    by_quote = {p["quote"]: b["item_id"] for b in builds for p in b["positions"]}
    inner = fake_generate(builds)
    turn = [0]

    def generate(prompt, answers, constraint=None):
        got = inner(prompt, answers)
        head, rest = got["reply"].split("```json" + chr(10), 1)
        body, tail = rest.split(chr(10) + "```", 1)
        obj = json.loads(body)
        if obj["wording"] != "whole":
            item = next(i for q, i in by_quote.items() if ("\n" + q + "\n") in prompt)
            art = next(a for a in sheets[item]["articles"] if a["id"] == obj["article"])
            text = nsl._spans(art)[int(obj["wording"]) - 1]
            turn[0] += 1
            obj["wording"] = ("[%s]" % text) if turn[0] % 2 else text
        got["reply"] = head + "```json" + chr(10) + json.dumps(obj) + chr(10) + "```" + tail
        return got
    return generate


def observe_reread_quotes():
    """read-pass on a pass whose model quoted its wordings: every label read, the labels the cards' own."""
    with tempfile.TemporaryDirectory() as tmp:
        fx = Fixture(tmp)
        prompts_path = Path(tmp) / "work" / "label_pass_prompts.json"
        build(fx, prompts_path)
        _code, archive, _folder, _ = run_pass(fx, prompts_path, Path(tmp) / "run", quoting_generate(fx.all_builds()))
        out = {}
        for name, path in zip(SETS, fx.paths):
            labels, record = nsl.read_pass(prompts_path, path, archive, CFG)
            cmp = ns.compare_labels(fx.cards[name], labels["labels"])
            out[name] = {"dropped": cmp["dropped_ids"], "perfect": cmp["mapping"]["kappa"] == 1.0,
                         "unread": sum(v for k, v in record["by_reason"].items() if k != "read")}
        return out


def expected_reread_quotes():
    one = {"dropped": [], "perfect": True, "unread": 0}
    return {"dev_1": one, "pilot_1": one}


def neutralise_reread_quotes():
    """The reader before this lane: answer_form's match against `whole` and the numbers alone."""
    return patch.object(nsl, "read_wording", lambda value, article, t: nsl.af.match(
        value, [t["whole"]] + [str(i) for i in range(1, nsl._wordings(article) + 1)]))


def observe_reread_new_names():
    """read-pass refuses an output that exists (the first reading is never overwritten) and writes a second
    reading under new names, its by_reason beside the first's."""
    with tempfile.TemporaryDirectory() as tmp:
        fx = Fixture(tmp)
        work = Path(tmp) / "work"
        prompts_path = work / "label_pass_prompts.json"
        build(fx, prompts_path)
        _code, archive, _folder, _ = run_pass(fx, prompts_path, Path(tmp) / "run")

        def read(suffix):
            argv = ["read-pass", "--prompts", str(prompts_path), "--sheets", str(fx.paths[0]), "--evidence",
                    str(archive), "--out", str(work / ("labels_dev_1%s.json" % suffix)),
                    "--record", str(work / ("LABELLER_dev_1%s.json" % suffix))]
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    nsl.main(argv)
                return "written"
            except SystemExit:
                return "refused"
        first = read("")
        before = (work / "labels_dev_1.json").read_bytes()
        (work / "labels_dev_1.json").write_bytes(b"{}")
        again = read("")
        kept = (work / "labels_dev_1.json").read_bytes() == b"{}"
        second = read("_r2")
        same = json.loads((work / "labels_dev_1_r2.json").read_bytes()) == json.loads(before)
        return {"first": first, "same_name_again": again, "first_kept": kept, "new_name": second,
                "same_labels": same}


def expected_reread_new_names():
    return {"first": "written", "same_name_again": "refused", "first_kept": True, "new_name": "written",
            "same_labels": True}


def neutralise_reread_new_names():
    return patch.object(nsl, "refuse_existing", lambda paths: None)


# ---------------------------------------------------------------------------
# lane/label-constrained (D-799, operator 19 November 2026 15:28): the reply generated under a per-request logits
# constraint. A tiny character tokenizer and a fake model whose logits push its own preferred reply; the real
# make_generate, LabelGrammar and DECODING-B's ContractProcessor run between them. No model, no download.

CONSTRAINED_SHEET = {"persona": {"id": "PX"}, "articles": [
    {"id": "A1", "text": "Alpha [beta gamma] delta [epsilon zeta] and [eta]."},
    {"id": "A2", "text": "Theta iota, no bracket."},
    {"id": "A3", "text": "One [mu] two [nu] three [xi] four [omicron] five [pi]."}]}
CONSTRAINED_POSITION = {"party": "PX"}
FAKE_DECODING = {"do_sample": False, "max_new_tokens": 160}


class CharTok:
    """A tiny tokenizer: id 0 the end-of-text token, then one id per printable ASCII character and the newline."""
    eos_token, eos_token_id = "<eos>", 0

    def __init__(self):
        self.chars = ["\n"] + [chr(c) for c in range(32, 127)]
        self.index = {c: i + 1 for i, c in enumerate(self.chars)}

    def __len__(self):
        return len(self.chars) + 1

    def encode(self, text, add_special_tokens=False):
        return [self.index[c] for c in text]

    def decode(self, ids, skip_special_tokens=True):
        return "".join(self.chars[i - 1] if i else ("" if skip_special_tokens else self.eos_token) for i in ids)

    def batch_decode(self, seqs, skip_special_tokens=True):
        return [self.decode(s, skip_special_tokens) for s in seqs]

    def apply_chat_template(self, messages, add_generation_prompt=True, return_tensors="pt"):
        import torch
        return torch.tensor([self.encode("<user>")])


class PreferModel:
    """A fake causal model: at each step its logits put 6.0 on the next character of its own preferred reply while
    the text so far is a prefix of it (the end-of-text token once it is all written), else a fixed seeded score
    per token; `random_steps` draws every step's scores afresh instead. generate() applies the logits processors
    as transformers does and returns sequences, scores (processed) and logits (raw)."""
    device = "cpu"

    def __init__(self, tok, prefer, seed=0, random_steps=False):
        import random as _random
        rng = _random.Random(seed)
        self.tok, self.prefer = tok, prefer
        self.base = [rng.random() for _ in range(len(tok))]
        self.base[0] = -1.0
        self.steps = _random.Random(seed + 1000) if random_steps else None

    def _logits(self, text):
        import torch
        row = [self.steps.random() * 4 for _ in range(len(self.tok))] if self.steps else list(self.base)
        if self.prefer and self.prefer.startswith(text):
            rest = self.prefer[len(text):]
            row[self.tok.index[rest[0]] if rest else 0] = 6.0
        return torch.tensor([row])

    def generate(self, ids, attention_mask=None, do_sample=None, max_new_tokens=1, pad_token_id=None,
                 output_scores=False, return_dict_in_generate=False, logits_processor=None, output_logits=False):
        import torch
        from types import SimpleNamespace
        if do_sample is not False:
            raise ValueError("the fake model decodes greedily only")
        seq, scores, raws = ids, [], []
        for _ in range(int(max_new_tokens)):
            raw = self._logits(self.tok.decode(seq[0, ids.shape[1]:].tolist()))
            s = logits_processor(seq, raw.clone()) if logits_processor is not None else raw
            nxt = int(s[0].argmax())
            seq = torch.cat([seq, torch.tensor([[nxt]])], dim=1)
            scores.append(s)
            raws.append(raw)
            if nxt == 0:
                break
        return SimpleNamespace(sequences=seq, scores=tuple(scores), logits=tuple(raws) if output_logits else None)


def _obj(article, wording, stance="oppose", firm="yes"):
    return json.dumps({"article": article, "wording": wording, "stance": stance, "firm_limit": firm})


PREFERRED = {
    "partial_quote": _obj("A1", "beta"),
    "changed_quote": _obj("A1", "[beta delta]"),
    "free_text": "The statement is about article A1; the party opposes its first bracketed wording.",
    "fenced_prose": "Here is my reading.\n```json\n" + _obj("A1", "the first wording") + "\n```"}


def _drive(prefer, constrained=True, seed=0, random_steps=False):
    """One call of the pass's own make_generate on a fresh fake tokenizer (so no cached state carries over)."""
    tok = CharTok()
    gen = lp.make_generate(PreferModel(tok, prefer, seed, random_steps), tok, FAKE_DECODING)
    answers = nsl.declared_answers(CONSTRAINED_SHEET, CONSTRAINED_POSITION, T)
    if not constrained:
        return gen("question", answers)
    return gen("question", answers, nsl.constraint_of(CONSTRAINED_SHEET, CONSTRAINED_POSITION, T))


def _read_label(reply):
    lab, why = nsl.read_answer(reply, CONSTRAINED_SHEET, CONSTRAINED_POSITION, T)
    return (why, None) if why else ("read", lab)


def observe_constraint_impossible():
    """A partial quote, a changed quote, free text and prose around the object, each the fake model's own
    preference: unconstrained, the reader refuses every one; constrained, every reply is inside the language and
    read, each with the steps where the model's top token was not admitted counted. Twenty random-score models
    under the constraint: every reply inside and read."""
    c = nsl.constraint_of(CONSTRAINED_SHEET, CONSTRAINED_POSITION, T)
    out = {}
    for name, prefer in PREFERRED.items():
        free, held = _drive(prefer, constrained=False), _drive(prefer)
        out[name] = {"free_read": _read_label(free["reply"])[0] == "read", "inside": lp.accepts(c, held["reply"]),
                     "constrained": _read_label(held["reply"])[0],
                     "intervened": (held["constraint"].get("interventions") or 0) > 0}
    replies = [_drive("", seed=s, random_steps=True)["reply"] for s in range(20)]
    out["random_inside_and_read"] = sum(1 for r in replies if lp.accepts(c, r) and _read_label(r)[0] == "read")
    return out


def expected_constraint_impossible():
    one = {"free_read": False, "inside": True, "constrained": "read", "intervened": True}
    return dict({name: one for name in PREFERRED}, random_inside_and_read=20)


def neutralise_constraint_impossible():
    import contract_decoding as cd
    return patch.object(cd.ContractProcessor, "__call__", lambda self, input_ids, scores: scores)


def observe_per_article_count():
    """The wording list is the decoded article's own: A1 has three bracketed wordings, A2 none, A3 five (so the
    sheet-wide list runs to 5). A model wanting A1's fifth or A2's second wording gets a value of that article's own
    list; a model wanting A1's third keeps it untouched; the confidence record's wording answers are the article's
    own too."""
    c = nsl.constraint_of(CONSTRAINED_SHEET, CONSTRAINED_POSITION, T)
    answers = nsl.declared_answers(CONSTRAINED_SHEET, CONSTRAINED_POSITION, T)

    def proposal(article, wording):
        got = _drive(_obj(article, wording))
        why, lab = _read_label(got["reply"])
        return {"read": why, "article": lab and lab["article"],
                "own_list": lab is not None and (lab["proposal"] is None or lab["proposal"] <= c["wording"]["per_article"][article]),
                "intervened": (got["constraint"].get("interventions") or 0) > 0}
    return {"language": {"A1_3": lp.accepts(c, _obj("A1", "3")), "A1_5": lp.accepts(c, _obj("A1", "5")),
                         "A2_1": lp.accepts(c, _obj("A2", "1")), "A2_whole": lp.accepts(c, _obj("A2", "whole")),
                         "A3_5": lp.accepts(c, _obj("A3", "5"))},
            "A1_wants_5": proposal("A1", "5"), "A2_wants_2": proposal("A2", "2"), "A1_wants_3": proposal("A1", "3"),
            "sheet_wide_answers": answers["wording"],
            "confidence_A1": lp.constrained_answers(answers, c, _obj("A1", "2")).get("wording"),
            "confidence_A2": lp.constrained_answers(answers, c, _obj("A2", "whole")).get("wording")}


def expected_per_article_count():
    kept = {"read": "read", "own_list": True}
    return {"language": {"A1_3": True, "A1_5": False, "A2_1": False, "A2_whole": True, "A3_5": True},
            "A1_wants_5": dict(kept, article="A1", intervened=True), "A2_wants_2": dict(kept, article="A2", intervened=True),
            "A1_wants_3": dict(kept, article="A1", intervened=False),
            "sheet_wide_answers": ["whole", "1", "2", "3", "4", "5"],
            "confidence_A1": ["whole", "1", "2", "3"], "confidence_A2": None}


def neutralise_per_article_count():
    """The sheet-wide list (1..the largest count) for every article, as the first pass declared it."""
    return patch.object(lp, "wording_values", lambda c, article: [c["wording"]["whole"]] + [
        str(i) for i in range(1, max(c["wording"]["per_article"].values()) + 1)])


def _v1_copy(value, path):
    """The v2 file as the first pass wrote its prompts: schema v1, no constraint block."""
    old = copy.deepcopy(value)
    old["schema"] = lp.SCHEMA
    for p in old["prompts"]:
        p.pop("constraint")
    Path(path).write_text(json.dumps(old, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return old


def observe_old_file_read():
    """A v1 prompts file (the saved first pass's form, no constraint) is still checked, run with the old two-argument
    generate, and read again by read-pass; build-pass now writes v2 with one constraint block a prompt."""
    with tempfile.TemporaryDirectory() as tmp:
        fx = Fixture(tmp)
        new_path, old_path = Path(tmp) / "work" / "p2.json", Path(tmp) / "work" / "p1.json"
        value = build(fx, new_path)
        _v1_copy(value, old_path)
        many = fake_generate(fx.all_builds())
        code, archive, folder, _ = run_pass(fx, old_path, Path(tmp) / "run",
                                            lambda prompt, answers: many(prompt, answers))
        m = json.loads((folder / lp.MEASUREMENT_FILE).read_text(encoding="utf-8"))
        records = [json.loads(p.read_text(encoding="utf-8")) for p in (folder / "audit" / "model_replies").glob("*.json")]
        labels, record = nsl.read_pass(old_path, fx.paths[0], archive, CFG)
        cmp = ns.compare_labels(fx.cards["dev_1"], labels["labels"])
        return {"v2_schema": value["schema"], "v2_constraints": all("constraint" in p for p in value["prompts"]),
                "v1_detected": lp.is_prompts_path(old_path), "v1_checked": _attempt(lambda: lp.load_prompts(old_path)),
                "v1_exit": code, "v1_constraint": m["constraint"], "v1_schema": m["prompts_schema"],
                "v1_record_unconstrained": not any("decoding_constraint" in r for r in records),
                "v1_perfect": cmp["mapping"]["kappa"] == 1.0, "v1_record_constraint": record["constraint_by_reason"]}


def expected_old_file_read():
    return {"v2_schema": lp.SCHEMA_V2, "v2_constraints": True, "v1_detected": True, "v1_checked": "built",
            "v1_exit": 0, "v1_constraint": None, "v1_schema": lp.SCHEMA, "v1_record_unconstrained": True,
            "v1_perfect": True, "v1_record_constraint": None}


def neutralise_old_file_read():
    return patch.object(lp, "SCHEMAS", (lp.SCHEMA_V2,))


def outside_generate(builds):
    """A fake generate under a v2 file that writes the oracle's object in the constrained form, except: its 1st
    reply in fenced prose (left the language), its 2nd cut off at the allowance, its 3rd cut off with a dead end
    recorded."""
    inner, turn = fake_generate(builds), [0]

    def generate(prompt, answers, constraint=None):
        got = inner(prompt, answers)
        o = json.loads(got["reply"].split("```json" + chr(10), 1)[1].split(chr(10) + "```", 1)[0])
        firm = o["firm_limit"] if o["firm_limit"] in constraint["values"]["firm_limit"] else constraint["values"]["firm_limit"][0]
        canonical = _obj(o["article"], str(o["wording"]), o["stance"], firm)
        turn[0] += 1
        record = {"name": lp.CONSTRAINT_NAME, "version": lp.CONSTRAINT_VERSION, "steps": 30, "interventions": 0,
                  "first_intervention_step": None, "dead_end": turn[0] == 3}
        reply, new = canonical, 30
        if turn[0] == 1:
            reply = got["reply"]
        elif turn[0] == 2:
            reply, new = canonical[:20], FAKE_DECODING["max_new_tokens"] * 10
        elif turn[0] == 3:
            reply = canonical[:25]
        return dict(got, reply=reply, new_tokens=new, constraint=record)
    return generate


def observe_outside_counted():
    """Every constrained reply's outcome is decided in Python and counted by reason in the pass record and, per set,
    in read-pass's record; none is read by guess (the reader drops the three cut or fenced ones by its own reason)."""
    with tempfile.TemporaryDirectory() as tmp:
        fx = Fixture(tmp)
        prompts_path = Path(tmp) / "work" / "p.json"
        value = build(fx, prompts_path)
        _code, archive, folder, _ = run_pass(fx, prompts_path, Path(tmp) / "run", outside_generate(fx.all_builds()))
        m = json.loads((folder / lp.MEASUREMENT_FILE).read_text(encoding="utf-8"))
        by = dict(m["constraint"]["by_reason"])
        inside = by.pop(lp.INSIDE, 0)
        per_set = Counter()
        for path in fx.paths:
            _labels, record = nsl.read_pass(prompts_path, path, archive, CFG)
            per_set.update(record["constraint_by_reason"])
        return {"outside_by_reason": by, "outside": m["constraint"]["outside"],
                "inside_is_rest": inside == value["prompt_count"] - 3, "sets_add_up": dict(per_set) == m["constraint"]["by_reason"]}


def expected_outside_counted():
    return {"outside_by_reason": {"left_language": 1, "at_allowance": 1, "dead_end": 1}, "outside": 3,
            "inside_is_rest": True, "sets_add_up": True}


def neutralise_outside_counted():
    return patch.object(lp, "outcome", lambda *a, **k: lp.INSIDE)


PROOFS = ("round_trip", "inputs_held", "model_sealed_only", "reply_held", "counts_only", "model_preflight",
          "wording_quote_exact", "wording_quote_ambiguous", "wording_quote_not_exact", "wording_marked_number",
          "wording_number_above_article", "reread_quotes", "reread_new_names", "constraint_impossible",
          "per_article_count", "old_file_read", "outside_counted")
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
