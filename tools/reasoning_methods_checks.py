"""Checks 475 and 476 (D-713, document review half): the two reasoning methods of
benchmark/baselines/reasoning_methods.py on the replay pass's claim and passage choice questions.

No model, no key, nothing launched: a fake backend whose `generate` writes canned step replies and
whose `choose` decides over a character vocabulary from fixed logits, on staged fixture workloads
(an invented harbour text and an invented score table) in a temporary folder. Every proof is run as
built (passes), neutralised (must fail), restored and run again (passes).

  475 reason_first: the rationale is a fixed field Python cuts from the reply, the label is decided
      over the form's own answers, an empty rationale never refuses, every call is one reply record
      with the runner's one-per-prompt count kept, the direct group is the shipped form byte for
      byte, and a config naming an undeclared method or a template with other slots is refused.
  476 stepwise: a cell id must be one Python listed, a quote must be found in its own passage and be
      its content, a tied comparison stops the chain, a refused step's record carries no decision,
      and the dropped-answer count and D-713's adoption rule read as declared.
"""
from __future__ import annotations

import contextlib
import inspect
import io
import json
import re
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "benchmark" / "baselines"
for _p in (str(BASELINES), str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "adapters")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import choice_decision as cd  # noqa: E402
import choice_judge  # noqa: E402
import doc_judge  # noqa: E402
import pair_judge  # noqa: E402
import reasoning_methods as rm  # noqa: E402
import reply_records  # noqa: E402

METHODS_CONFIG = BASELINES / "choice_methods_prompt.json"
SHIPPED_CONFIG = BASELINES / "choice_judge_prompt.json"
VOCABULARY = 256
READER = {"backend": "local_auditor", "agent": "PRACTICE_AUDITOR", "model_id": "fixture/model", "model_mode": "base",
          "decoding": {"kwargs": {"do_sample": False, "eos_token_id": [1], "pad_token_id": 1}, "status": "restored",
                       "source": "fixture", "sha256": "0" * 64}}
PAIR_TEXT = ("The northern quay was leased to the first tenant of the harbour in spring.\n\n"
             "The southern quay stayed empty through the whole of that year.\n\n"
             "The northern quay was never leased to anyone in spring.\n")
TABLE_TEXT = ("Table 2: Scores of the compared systems.\n\n| Model | Acc | F1 score |\n|---|---|---|\n| GloVe vectors | 71.2 | 60 |\n"
              "| BERT large | 80.1 | 70 |\n| Word2Vec | 50 | 40 |\n")
CLAIM = "BERT large has a higher F1 score than GloVe vectors."
_PASSAGES = re.compile(r"PASSAGE A\n(.*?)\n\nPASSAGE B\n(.*?)\n\n", re.S)


def encode(text):
    return [ord(c) % VOCABULARY for c in text]


def logits(**by_letter):
    row = [0.0] * VOCABULARY
    for letter, value in by_letter.items():
        row[ord(letter)] = value
    return row


def step_of(user):
    if "Do not answer yet." in user:
        return "rationale"
    if "Copy, word for word," in user or "Which cells does the claim rest on?" in user:
        return "evidence"
    return None


def default_text(step, user):
    if step == "rationale":
        return "Reasoning: the second row's figure is the higher one.\nAnswer: Yes\n{\"outcome\": \"holds\"}"
    if "Which cells" in user:
        return "Cells: R2C2, R1C2"
    first, second = _PASSAGES.search(user).groups()
    return "A: \"%s\"\nB: %s" % (" ".join(first.split()[:4]), " ".join(second.split()[:4]))


def default_logits(step):
    return {"C": 3.0, "A": 1.0, "U": 1.0, "I": 1.0} if step == "comparison" else {"Y": 3.0, "N": 2.0, "U": 1.0}


class Backend:
    """A canned model on the replay's backend: writes the script's step replies, decides over the
    character vocabulary from the script's logits, and keeps every call it was asked."""

    def __init__(self, reader, script, calls):
        self.reader, self.script, self.calls = reader, script, calls

    def prepare(self):
        return {"model_id": self.reader["model_id"], "digest": "fixture", "checkpoint": {"checkpoint": "base"}}

    def max_context(self):
        return self.script.get("context", 10 ** 6)

    def count_prompt(self, system, user):
        return len(user.split())

    def generate(self, system, user, max_new_tokens):
        step = step_of(user)
        text = self.script.get("text", default_text)(step, user)
        self.calls.append({"op": "generate", "step": step, "user": user, "allowance": max_new_tokens, "system": system})
        return {"text": text, "payload": user, "form": "rendered_prompt", "output_tokens": len(text.split()),
                "prefill": {"prefill_seconds": .01, "chunks": 0}}

    def choose(self, system, user, answers):
        step = "comparison" if {a["label"] for a in answers} & {"agree", "agrees"} else "label"
        self.calls.append({"op": "choose", "step": step, "user": user, "labels": [a["label"] for a in answers], "system": system})
        row = logits(**self.script.get("logits", default_logits)(step))
        decision = dict(cd.decide(lambda p: row, cd.bind(cd.declare(user, answers), encode), None), logits_dtype="fixture")
        return {"decision": decision, "payload": user, "form": "rendered_prompt", "attention": {"pinned": True},
                "prefill": {"prefill_seconds": .01, "chunks": 0}}

    def release(self):
        pass


def _workload(folder, name, text, rules, benchmark):
    folder = Path(folder) / name
    (folder / "context").mkdir(parents=True)
    (folder / "conventions").mkdir()
    (folder / "context" / (name + ".md")).write_text(text, encoding="utf-8")
    (folder / "context" / "_review_targets.json").write_text(json.dumps({"targets": [name + ".md"]}), encoding="utf-8")
    (folder / "conventions" / "review_conventions.md").write_text(
        "\n".join("## %s\n\n%s\n" % (k, v) for k, v in rules.items()), encoding="utf-8")
    items = folder / "items.json"
    items.write_text(json.dumps([{"document_id": name, "item_id": "i-" + k, "rule_id": k, "benchmark": benchmark} for k in rules]),
                     encoding="utf-8")
    return folder, items


def config_with(folder, groups=None, edit=None):
    """The measurement config, with only the named groups, edited by `edit`, in `folder`."""
    value = json.loads(METHODS_CONFIG.read_text(encoding="utf-8"))
    if groups is not None:
        value["models"] = [g for g in value["models"] if g["group"] in groups]
    if edit:
        edit(value)
    path = Path(folder) / ("config_%d.json" % len(list(Path(folder).glob("config_*.json"))))
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def built(folder, config_path, pairs=True, claims=True):
    folder = Path(folder)
    kwargs = {}
    if pairs:
        w, i = _workload(folder, "pairs", PAIR_TEXT, {"CONV-X": "No passage may state what another rules out."}, "contradoc")
        kwargs.update(pair_workloads=[w], pair_items=[i])
    if claims:
        rule = doc_judge._adapter("scitab").RULE_TEMPLATE.format(claim=CLAIM)
        w, i = _workload(folder, "claims", TABLE_TEXT, {"CONV-1": rule}, "scitab")
        kwargs.update(claim_workloads=[w], claim_items=[i])
    out = folder / "prompts.json"
    with patch.object(pair_judge, "_words_allowed", True):
        value = choice_judge.build(out, config_path=config_path, embed=lambda items: None, **kwargs)
    return out, value


def a_pass(folder, script=None, groups=None, pairs=True, claims=True, edit=None):
    folder = Path(folder)
    out, value = built(folder, config_with(folder, groups, edit), pairs, claims)
    run, calls = folder / "run", []
    measurement = doc_judge.run(out, run, backend_factory=lambda r, c: Backend(r, script or {}, calls),
                                reader_for=lambda g, a: dict(READER))
    main = reply_records.records(run / "audit" / "model_replies")
    side = reply_records.records(run / rm.STEPS_DIR / "audit" / "model_replies")
    return {"out": out, "value": value, "run": run, "measurement": measurement, "calls": calls, "main": main, "side": side,
            "rows": {r["prompt_id"]: r for r in measurement["rows"]}, "by_call": {r["call_id"]: r for r in main}}


def caught(function):
    try:
        return function()
    except Exception as exc:     # a neutralised run's error is its observation
        return "raised " + type(exc).__name__


def with_source(owner, name, old, new):
    """`owner.name` with one line of its own source changed, as a neutralisation."""
    function = getattr(owner, name)
    source = textwrap.dedent(inspect.getsource(function))
    if source.count(old) != 1:
        raise AssertionError("the neutralisation's line is not in %s once: %s" % (name, old))
    space = dict(vars(sys.modules[function.__module__]))
    exec(source.replace(old, new), space)
    return patch.object(owner, name, space[name])


def _rows_of(seen, group):
    return [r for r in seen["measurement"]["rows"] if r["group"] == group]


# ---------------------------------------------------------------------------
# 475 reason_first


def observe_reason_first_separates():
    with tempfile.TemporaryDirectory() as folder:
        seen = a_pass(folder, groups={"choice_reason_first"})
        labels = [c for c in seen["calls"] if c["step"] == "label"]
        return {"label_calls": len(labels) == seen["value"]["prompt_count"],
                "rationale_shown": all("REASONING\nthe second row's figure is the higher one.\n\n" in c["user"] for c in labels),
                "rest_never_shown": not any("Answer: Yes" in c["user"] or "outcome" in c["user"] for c in labels),
                "label_over_form_answers": sorted({tuple(sorted(c["labels"])) for c in labels}),
                "decided": sorted({(seen["by_call"][r["call_id"]].get("decision") or {}).get("top") or "none" for r in _rows_of(seen, "choice_reason_first")}),
                "kept_chars": sorted({r["steps"][0].get("kept_chars") for r in _rows_of(seen, "choice_reason_first")})}


def expected_reason_first_separates():
    return {"label_calls": True, "rationale_shown": True, "rest_never_shown": True,
            "label_over_form_answers": [("cannot be settled", "holds", "not met"), ("cannot tell", "contradicts", "does not")],
            "decided": ["contradicts", "holds"], "kept_chars": [len("the second row's figure is the higher one.")]}


def neutralise_reason_first_separates():
    return patch.object(rm, "rationale", lambda text, method: str(text))


def observe_one_record_per_call():
    import ordinary_final_run
    with tempfile.TemporaryDirectory() as folder:
        seen = a_pass(folder)
        count = seen["value"]["prompt_count"]
        counted = ordinary_final_run.replay_observation(seen["run"], count, ["sdpa"])
        method_rows = [r for r in seen["measurement"]["rows"] if r.get("method")]
        return {"runner_count_kept": counted["items_without_one_record"] == [] and counted["reply_records"] == count,
                "every_call_one_record": len(seen["main"]) + len(seen["side"]) == len(seen["calls"]),
                "steps_listed": all(len(r["steps"]) == (2 if r["method"] == rm.REASON_FIRST else 3) for r in method_rows),
                "earlier_steps_aside": all(all(s.get("call_id") for s in r["steps"][:-1]) for r in method_rows),
                "no_text_in_rows": not any("user" in s or "text" in s for r in method_rows for s in r["steps"]),
                "methods": sorted({r.get("method") or "direct" for r in seen["measurement"]["rows"]})}


def expected_one_record_per_call():
    return {"runner_count_kept": True, "every_call_one_record": True, "steps_listed": True, "earlier_steps_aside": True,
            "no_text_in_rows": True, "methods": ["direct", "reason_first", "stepwise"]}


def neutralise_one_record_per_call():
    return patch.object(rm, "STEPS_DIR", ".")


def observe_direct_unchanged():
    with tempfile.TemporaryDirectory() as folder:
        seen = a_pass(folder)
        direct = [p for p in seen["value"]["prompts"] if p["group"] == "choice_direct"]
        asked = [c for c in seen["calls"] if c["user"] in {p["user"] for p in direct}]
        Path(folder, "shipped").mkdir()
        shipped = built(Path(folder) / "shipped", SHIPPED_CONFIG)[1]["prompts"]
        return {"direct_calls": len(asked) == len(direct) and all(c["op"] == "choose" for c in asked),
                "no_method_rows": not any(r.get("method") or r.get("steps") for r in _rows_of(seen, "choice_direct")),
                "same_questions_as_shipped": [p["user"] for p in direct] == [p["user"] for p in shipped],
                "shipped_declares_no_method": "methods" not in json.loads(SHIPPED_CONFIG.read_text(encoding="utf-8"))["choice"]}


def expected_direct_unchanged():
    return {"direct_calls": True, "no_method_rows": True, "same_questions_as_shipped": True, "shipped_declares_no_method": True}


def neutralise_direct_unchanged():
    return patch.object(rm, "method_of", lambda group: rm.REASON_FIRST)


def observe_rationale_never_refuses():
    with tempfile.TemporaryDirectory() as folder:
        script = {"text": lambda step, user: ""}
        seen = a_pass(folder, script, groups={"choice_reason_first"}, pairs=False)
        rows = _rows_of(seen, "choice_reason_first")
        return {"refused": [r.get("method_refused") for r in rows], "decided": [bool(seen["by_call"][r["call_id"]].get("decision")) for r in rows],
                "empty_shown": all("REASONING\n\n\n" in c["user"] for c in seen["calls"] if c["step"] == "label"),
                "dropped": rm.dropped(seen["measurement"]["rows"])["choice_reason_first"]["dropped"]}


def expected_rationale_never_refuses():
    return {"refused": [None], "decided": [True], "empty_shown": True, "dropped": 0}


def neutralise_rationale_never_refuses():
    return with_source(rm, "run_method", 'first["kept_chars"] = len(values["reasoning"])',
                       'first["kept_chars"] = len(values["reasoning"]) or (_ for _ in ()).throw(StepRefused("rationale_empty"))')


def observe_config_refusals():
    out = {}
    with tempfile.TemporaryDirectory() as folder:
        def undeclared(value):
            del value["choice"]["methods"]["stepwise"]

        def other_slots(value):
            value["choice"]["methods"]["reason_first"]["forms"]["pair"]["label"] = "{passage_a} {passage_b} no reasoning slot"

        def unknown(value):
            value["models"][1]["method"] = "majority_vote"
        for name, edit in (("undeclared", undeclared), ("other_slots", other_slots), ("unknown", unknown)):
            path = config_with(folder, None, edit)
            out[name] = caught(lambda: doc_judge.load_config(path) and "loaded")
        out["shipped"] = caught(lambda: doc_judge.load_config(SHIPPED_CONFIG) and "loaded")
        out["methods"] = caught(lambda: doc_judge.load_config(METHODS_CONFIG) and "loaded")
    return out


def expected_config_refusals():
    return {"undeclared": "raised ValueError", "other_slots": "raised ValueError", "unknown": "raised ValueError",
            "shipped": "loaded", "methods": "loaded"}


def neutralise_config_refusals():
    return patch.object(rm, "check", lambda choice, groups: None)


# ---------------------------------------------------------------------------
# 476 stepwise


def _stepwise(folder, script, pairs=False, claims=True, edit=None):
    return a_pass(folder, script, groups={"choice_stepwise"}, pairs=pairs, claims=claims, edit=edit)


def _one_cell(value):
    value["choice"]["methods"]["stepwise"]["max_cells"] = 1


def observe_claim_cells_checked():
    out = {}
    for name, reply, edit in (("listed", "Cells: R2C2, R1C2", None), ("not_listed", "Cells: R9C9", None),
                              ("none", "I cannot tell.", None), ("too_many", "Cells: R2C2, R1C2", _one_cell)):
        with tempfile.TemporaryDirectory() as folder:
            seen = caught(lambda: _stepwise(folder, {"text": lambda step, user, reply=reply: reply}, edit=edit))
            if isinstance(seen, str):
                out[name] = seen
                continue
            row = _rows_of(seen, "choice_stepwise")[0]
            compared = [c for c in seen["calls"] if c["step"] == "comparison"]
            out[name] = {"refused": (row.get("method_refused") or {}).get("reason"), "comparisons": len(compared),
                         "python_cells": bool(compared) and "R2C2: BERT large / F1 score = 70\nR1C2: GloVe vectors / F1 score = 60" in compared[0]["user"],
                         "label_asked": any(c["step"] == "label" for c in seen["calls"])}
    return out


def expected_claim_cells_checked():
    return {"listed": {"refused": None, "comparisons": 1, "python_cells": True, "label_asked": True},
            "not_listed": {"refused": rm.CELL_NOT_SHOWN, "comparisons": 0, "python_cells": False, "label_asked": False},
            "none": {"refused": rm.NO_CELL_NAMED, "comparisons": 0, "python_cells": False, "label_asked": False},
            "too_many": {"refused": rm.TOO_MANY_CELLS, "comparisons": 0, "python_cells": False, "label_asked": False}}


def neutralise_claim_cells_checked():
    return with_source(rm, "cited_cells", "if any(cid not in listed for cid in named):", "if False:")


def observe_pair_quotes_checked():
    out = {}

    def quote(kind):
        def text(step, user):
            first, second = _PASSAGES.search(user).groups()
            a = " ".join(first.split()[:4])
            b = {"found": " ".join(second.split()[:4]), "not_found": "a quay of glass", "piece": second.split()[1][1:],
                 "missing": None}[kind]
            return "A: %s" % a + ("" if b is None else "\nB: %s" % b)
        return text
    for kind in ("found", "not_found", "piece", "missing"):
        with tempfile.TemporaryDirectory() as folder:
            seen = caught(lambda: _stepwise(folder, {"text": quote(kind)}, pairs=True, claims=False))
            if isinstance(seen, str):
                out[kind] = seen
                continue
            rows = _rows_of(seen, "choice_stepwise")
            out[kind] = {"refused": sorted({str((r.get("method_refused") or {}).get("reason")) for r in rows}),
                         "comparisons": len([c for c in seen["calls"] if c["step"] == "comparison"]) == (len(rows) if kind == "found" else 0)}
    return out


def expected_pair_quotes_checked():
    return {"found": {"refused": ["None"], "comparisons": True}, "not_found": {"refused": [rm.QUOTE_NOT_FOUND], "comparisons": True},
            "piece": {"refused": [rm.QUOTE_NOT_CONTENT], "comparisons": True}, "missing": {"refused": [rm.QUOTE_MISSING], "comparisons": True}}


def neutralise_pair_quotes_checked():
    return with_source(rm, "cited_quotes", "if quote not in _norm(passage):", "if False:")


def observe_comparison_tie_refused():
    with tempfile.TemporaryDirectory() as folder:
        script = {"logits": lambda step: {"A": 1.0, "C": 1.0, "I": 0.0} if step == "comparison" else {"Y": 3.0, "N": 2.0, "U": 1.0}}
        seen = caught(lambda: _stepwise(folder, script))
        if isinstance(seen, str):
            return seen
        row = _rows_of(seen, "choice_stepwise")[0]
        record = seen["by_call"][row["call_id"]]
        return {"refused": row.get("method_refused"), "label_asked": any(c["step"] == "label" for c in seen["calls"]),
                "record_ok": record.get("backend_ok"), "record_decision": record.get("decision"),
                "record_error": record.get("error"),
                "dropped": rm.dropped(seen["measurement"]["rows"])["choice_stepwise"]}


def expected_comparison_tie_refused():
    return {"refused": {"step": "comparison", "reason": rm.COMPARISON_TIE}, "label_asked": False, "record_ok": False,
            "record_decision": None, "record_error": "method_refused: comparison comparison_tie",
            "dropped": {"prompts": 1, "decided": 0, "dropped": 1, "by_reason": {"comparison:comparison_tie": 1}, "rate": 1.0}}


def neutralise_comparison_tie_refused():
    return with_source(doc_judge, "run", 'result = dict(steps[-1]["result"] or {}, decision=None)',
                       'result = dict(steps[-1]["result"] or {})')


def observe_label_step_shows_checked_steps():
    with tempfile.TemporaryDirectory() as folder:
        seen = _stepwise(folder, {})
        label = [c for c in seen["calls"] if c["step"] == "label"][0]
        row = _rows_of(seen, "choice_stepwise")[0]
        record = seen["by_call"][row["call_id"]]
        return {"evidence": "EVIDENCE\nR2C2: BERT large / F1 score = 70\nR1C2: GloVe vectors / F1 score = 60\n\n" in label["user"],
                "comparison": "COMPARISON\nThe cited cells conflict with what the claim states.\n\n" in label["user"],
                "label_answers": sorted(label["labels"]),
                "record_answers": sorted(a["label"] for a in record["decision"]["answers"]),
                "steps": [(s["step"], s["check"]) for s in row["steps"]], "compared": row["steps"][1].get("compared")}


def expected_label_step_shows_checked_steps():
    return {"evidence": True, "comparison": True, "label_answers": ["cannot be settled", "holds", "not met"],
            "record_answers": ["cannot be settled", "holds", "not met"],
            "steps": [("evidence", "ok"), ("comparison", "ok"), ("label", "ok")], "compared": "conflicts"}


def neutralise_label_step_shows_checked_steps():
    return with_source(rm, "run_method", 'values["comparison"] = next(a["shown"] for a in spec["answers"] if a["label"] == decision["top"])',
                       'values["comparison"] = decision["top"]')


def observe_adoption_rule():
    bar = {"accuracy": 0.60, "flag_f1": 0.60}
    direct = {"contradoc_dev": {"accuracy": 0.55, "flag_f1": 0.40, "dropped_rate": 0.02},
              "scitab_dev": {"accuracy": 0.62, "flag_f1": 0.50, "dropped_rate": 0.01}}
    better = {"contradoc_dev": {"accuracy": 0.58, "flag_f1": 0.45, "dropped_rate": 0.02},
              "scitab_dev": {"accuracy": 0.61, "flag_f1": 0.55, "dropped_rate": 0.01}}
    rose = {k: dict(v, dropped_rate=v["dropped_rate"] + 0.03) for k, v in better.items()}
    away = dict(better, scitab_dev=dict(better["scitab_dev"], flag_f1=0.45))
    one_set = {"contradoc_dev": better["contradoc_dev"]}
    rows = [{"form": "choice", "group": "g", "failure": None}, {"form": "choice", "group": "g", "failure": "out_of_memory"},
            {"form": "choice", "group": "g", "failure": None, "method_refused": {"step": "evidence", "reason": "cell_not_shown"}},
            {"form": "b1", "group": "g", "failure": "x"}]
    return {"better": rm.adopt(direct, better, bar)[0], "rose": rm.adopt(direct, rose, bar)[0], "away": rm.adopt(direct, away, bar)[0],
            "one_set": rm.adopt(direct, one_set, bar)[0], "dropped": rm.dropped(rows)["g"]}


def expected_adoption_rule():
    return {"better": True, "rose": False, "away": False, "one_set": False,
            "dropped": {"prompts": 3, "decided": 1, "dropped": 2, "by_reason": {"out_of_memory": 1, "evidence:cell_not_shown": 1},
                        "rate": 2 / 3}}


def neutralise_adoption_rule():
    return with_source(rm, "adopt", 'or m["dropped_rate"] > d["dropped_rate"]:', ':')


GROUPS = {
    "475": ("reason_first_separates", "one_record_per_call", "direct_unchanged", "rationale_never_refuses", "config_refusals"),
    "476": ("claim_cells_checked", "pair_quotes_checked", "comparison_tie_refused", "label_step_shows_checked_steps", "adoption_rule"),
}


def _proof(name):
    space = globals()
    return space["observe_" + name], space["expected_" + name], space["neutralise_" + name]


def run_group(number):
    done = []
    for name in GROUPS[number]:
        observe, expected, neutralise = _proof(name)
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                first = observe()
                with neutralise():
                    broken = caught(observe)
                again = observe()
        except Exception as exc:
            return "FAIL", "%s: %s %s" % (name, type(exc).__name__, str(exc)[:300])
        if first != expected():
            return "FAIL", "%s as built: %s" % (name, str(first)[:400])
        if broken == expected():
            return "FAIL", "%s still passes when neutralised" % name
        if again != expected():
            return "FAIL", "%s after restore: %s" % (name, str(again)[:400])
        done.append(name)
    return "PASS", "%d proofs, each neutralise, fail, restore, pass, on a fake backend and fixture workloads: %s" % (len(done), ", ".join(done))


if __name__ == "__main__":
    status, detail = run_group(sys.argv[1] if len(sys.argv) > 1 else "475")
    print(status, detail)
    raise SystemExit(0 if status == "PASS" else 1)
