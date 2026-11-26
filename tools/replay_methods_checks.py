#!/usr/bin/env python3
"""Checks 515 and 516 (lane/replay-methods): the two builder pieces two blocked night runs wait for.

515, S0 (docs/loop/stages/NEG_ROUND1.md section 6, D-713): the negotiation advisor's step-wise chain on the
    replay pass. A system advice group declaring `method: stepwise` in its prompts file's own config runs,
    through benchmark/baselines/replay_prompts.py's `run`, the chain of neg_advisor.stepwise_advice on the
    resident model (generated steps within the method's allowance, choice steps decided over their declared
    answers at the method's threshold, CHOICE-A), each answer checked by Python before the next; one reply
    record per step, the last in the pass folder as the prompt's own; `answers` (and the re-reader,
    ANSWER-FORM-A) compose the reply again from the saved steps, each held to the SHA-256 the pass recorded;
    the system's audits are derived from the composed reply. Off unless the file declares the method.
516, open item 148 (b): one prompts file of several model groups (choice_direct, choice_reason_first,
    choice_stepwise) is read by choice_read one group a candidate (NAME=PROMPTS,RUN#GROUP): a file of several
    groups is refused unread whole, each method candidate reads only the group declaring its method, binds to
    the base by its questions, and carries its own dropped-answer figure.
518, D-725 (lane/mplain-fix2): M-plain's advice allowance is a declared config value,
    `advice.methods.plain.max_new_tokens` in benchmark/baselines/neg_advisor_prompt.json (4,096), read by
    neg_advisor.advice_allowance when a prompt is built and again when it is loaded; D-740: reason_first's
    equal `advice.methods.reason_first.max_new_tokens` (4,096) read the same way; B1 and stepwise keep
    `advice.max_new_tokens`; check_config refuses an allowance that is not a positive integer; a prompt
    carrying another allowance than its config is refused.

No model, no key, no item, nothing launched: fake backends on the invented fixtures of
tools/neg_advisor_checks.py and tools/reasoning_methods_checks.py, in temporary folders. Every proof is run
as built (passes), neutralised (must fail), restored and run again (passes).
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "benchmark" / "baselines"), str(ROOT / "scripts"), str(ROOT / "tools"),
           str(ROOT / "benchmark" / "adapters")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_advisor as na  # noqa: E402
import neg_advisor_checks as nb  # noqa: E402
import reasoning_methods_checks as rmc  # noqa: E402
import reply_records  # noqa: E402

caught, with_source = rmc.caught, rmc.with_source
WORDING = "Each party shall report outbreak data within a period it sets"


# ---------------------------------------------------------------------------
# 515 the step-wise chain on the replay pass


def stance_of(user):
    return next(p["stance"] for p in nb.BUILD["positions"] if p["quote"] in user)


class StepBackend(nb.FakeBackend):
    """The advisor checks' fake model, answering the step-wise questions too: `changes` with the proposal's
    first six words, `wording` with a fixed line, stance by the fixture's own stance of the quoted position,
    a red line by the script, an open point yes on the data-sharing proposal. `tie` makes every stance
    choice a tie (unsettled)."""
    script = {}

    def generate(self, system, user, n):
        if "What does this proposal change?" in user and self.script.get("changes"):
            # Issue #322: `changes` answers with `text` and reports `tokens` generated (n is the allowance).
            text, tokens = self.script["changes"]
            return {"text": text, "payload": user, "form": "rendered_prompt",
                    "output_tokens": n if tokens == "cap" else tokens}
        if "What does this proposal change?" in user:
            return {"text": " ".join(user.splitlines()[1].split(": ", 1)[1].split()[:6]), "payload": user,
                    "form": "rendered_prompt"}
        if "Write one middle-ground wording" in user:
            return {"text": WORDING, "payload": user, "form": "rendered_prompt"}
        return dict(super().generate(system, user, n), payload=user, form="rendered_prompt")

    def choose(self, system, user, answers):
        labels = {a["label"] for a in answers}
        calls = self.script.setdefault("_calls", [0])
        calls[0] += 1
        if self.script.get("raise_at") == calls[0]:
            raise RuntimeError("the fake model stops at call %d" % calls[0])
        if self.script.get("audit_tie") and user.startswith("A negotiation advisor gave") and "P-A1-2" in user:
            rows = [{"label": a["label"], "surface": a["surface"], "token_id": k, "probability": 1 / len(answers)}
                    for k, a in enumerate(answers)]
            return {"decision": {"schema": "choice-decision-v1", "answers": rows, "declared_mass": 1.0},
                    "payload": user, "form": "rendered_prompt"}
        if labels == set(na.POSITION_STANCES):
            wanted = None if self.script.get("tie") else stance_of(user)
        elif labels == {"yes", "no"}:
            wanted = (self.script.get("red_line", "yes") if "cross this red line" in user
                      else "yes" if "share outbreak data" in user else "no")
        else:
            return super().choose(system, user, answers)
        rows = [{"label": a["label"], "surface": a["surface"], "token_id": k,
                 "probability": (1 / len(answers)) if wanted is None else 0.9 if a["label"] == wanted
                 else 0.1 / (len(answers) - 1)} for k, a in enumerate(answers)]
        return {"decision": {"schema": "choice-decision-v1", "answers": rows, "declared_mass": 1.0},
                "payload": user, "form": "rendered_prompt"}


def config_file(folder, method):
    value = na.load_config()
    for g in value["models"]:
        if g["group"] == "system_advice" and method is not None:
            g["method"] = method
    path = Path(folder) / ("config_%s.json" % (method or "plain"))
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def replay(method="stepwise", script=None, tamper=None):
    """The fixture item's system advice built under `method`, run through replay_prompts.py's own `run`
    command (the sealed pass's entry), then read by neg_advisor.answers and the re-reader."""
    import replay_prompts
    import reread_replies as rr
    with nb.setdir() as root, tempfile.TemporaryDirectory(prefix="replaym_") as td:
        prompts = Path(td) / "prompts.json"
        na.build(root, "advice", ["system_advice"], prompts, config_path=config_file(td, method))
        out = Path(td) / "pass"
        backend = type("Scripted", (StepBackend,), {"script": dict(script or {})})
        with patch.object(na, "make_advisor_backend", backend), patch.object(na, "reader_of", nb.fake_reader), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = replay_prompts.main(["run", "--prompts", str(prompts), "--out", str(out), "--paths", "sdpa"])
        if code != 0 and not (out / na.MEASUREMENT_FILE).is_file():
            return {"replay": code}
        measurement = json.loads((out / na.MEASUREMENT_FILE).read_text(encoding="utf-8"))
        if tamper:
            tamper(measurement)
            (out / na.MEASUREMENT_FILE).write_text(json.dumps(measurement), encoding="utf-8")
        main = reply_records.records(out / "audit" / "model_replies")
        side_dir = out / na.STEPWISE_DIR / "audit" / "model_replies"
        side = reply_records.records(side_dir) if side_dir.is_dir() else []
        answers = caught(lambda: na.answers(prompts, out))
        again = caught(lambda: rr.advisor_answers(prompts, out))
        return {"measurement": measurement, "main": main, "side": side, "answers": answers, "again": again, "code": code}


def _pieces(row):
    reply = row.get("reply") or {}
    return {pid: (e.get("conflict"), e.get("stance"), bool(e.get("wording"))) for pid, e in sorted((reply.get("proposals") or {}).items())}


def _row(seen):
    return next(r for r in seen["answers"]["rows"] if r["group"] == "system_advice")


def observe_chain_on_the_replay_pass():
    seen = replay()
    if "measurement" not in seen or isinstance(seen["answers"], str):
        return {"failed": str(seen.get("replay") or seen.get("answers"))}
    m, row = seen["measurement"], _row(seen)
    again = seen["again"] if isinstance(seen["again"], str) else next(r for r in seen["again"]["rows"] if r["group"] == "system_advice")
    return {"pieces": _pieces(row), "method": row.get("method"), "steps": m.get("steps"),
            "asked": sorted(Counter(r["step"] for r in m["rows"] if r["form"] == na.STEP_FORM).items()),
            "records_in_pass": len(seen["main"]), "records_aside": len(seen["side"]), "derived_audits": m.get("derived"),
            "audit": row.get("audit"), "reread_same": not isinstance(again, str) and _pieces(again) == _pieces(row),
            "reread_drops": None if isinstance(again, str) else again.get("drops"),
            "rows_without_text": not any("text" in r or "user" in r for r in m["rows"])}


def expected_chain_on_the_replay_pass():
    # The conflict Python composes from the checked stances is the fixture key's (check 468), here asked on the
    # replay pass: 14 step calls, the item's last in the pass folder beside the 3 audits, 13 aside.
    return {"pieces": {"P-A1-1": ("no_conflict", "accept", False), "P-A1-2": ("not_stated", "counter", True),
                       "P-A2-1": ("conflict", "reject", False)},
            "method": "stepwise", "steps": 14,
            "asked": [("changes", 3), ("open_point", 3), ("red_line", 1), ("stance", 6), ("wording", 1)],
            "records_in_pass": 4, "records_aside": 13, "derived_audits": 3,
            "audit": {"P-A1-1": "supported", "P-A1-2": "unsupported", "P-A2-1": "supported"},
            "reread_same": True, "reread_drops": {}, "rows_without_text": True}


def neutralise_chain_on_the_replay_pass():
    return patch.object(na, "is_stepwise", lambda config, prompt: False)


def observe_each_step_checked():
    seen = replay(script={"tie": True})
    if "measurement" not in seen or isinstance(seen["answers"], str):
        return {"failed": str(seen.get("replay") or seen.get("answers"))}
    row = _row(seen)
    return {"pieces": _pieces(row), "refused": row.get("steps_refused"), "steps": seen["measurement"]["steps"],
            "audits": seen["measurement"]["derived"]}


def expected_each_step_checked():
    # A tied stance settles to no declared answer: Python refuses it and that proposal's chain ends, nothing
    # composed for it, no audit derived; P-A1-2 has no position on it, so its chain runs to its counter.
    return {"pieces": {"P-A1-1": (None, None, False), "P-A1-2": ("not_stated", "counter", True), "P-A2-1": (None, None, False)},
            "refused": {"stance:not_declared": 2}, "steps": 7, "audits": 1}


def neutralise_each_step_checked():
    return patch.object(na, "_step_check", lambda step, answer, item, proposal, position=None: (answer, None))


def observe_off_unless_declared():
    out = {}
    for method in (None, "stepwise"):
        seen = replay(method=method)
        if "measurement" not in seen:
            out[str(method)] = "failed"
            continue
        out[str(method)] = {"steps": seen["measurement"].get("steps"), "aside": len(seen["side"]),
                            "method": None if isinstance(seen["answers"], str) else _row(seen).get("method")}
    return out


def expected_off_unless_declared():
    return {"None": {"steps": 0, "aside": 0, "method": None}, "stepwise": {"steps": 14, "aside": 13, "method": "stepwise"}}


def neutralise_off_unless_declared():
    return patch.object(na, "method_of", lambda config, group: na.STEPWISE if group == "system_advice" else na.PLAIN)


def _swap_step_hash(measurement):
    step = next(r for r in measurement["rows"] if r["form"] == na.STEP_FORM and r["step"] == "stance")
    step["user_sha256"] = "0" * 64


def _drop_last_step(measurement):
    last = max(i for i, r in enumerate(measurement["rows"]) if r["form"] == na.STEP_FORM)
    del measurement["rows"][last]


def observe_recomposed_from_saved_steps():
    out = {}
    for name, tamper in (("as_saved", None), ("question_changed", _swap_step_hash), ("step_missing", _drop_last_step)):
        seen = replay(tamper=tamper)
        answers = seen.get("answers")
        out[name] = (answers[:30] if isinstance(answers, str) else _pieces(_row(seen))) if "measurement" in seen else "failed"
    return out


def expected_recomposed_from_saved_steps():
    return {"as_saved": expected_chain_on_the_replay_pass()["pieces"], "question_changed": "raised ValueError",
            "step_missing": "raised ValueError"}


def neutralise_recomposed_from_saved_steps():
    return with_source(na, "recompose_stepwise",
                       'if row.get("step") != step or row.get("user_sha256") != _sha(user):', 'if False:')


def _records(seen):
    return seen["main"] + seen["side"]


def observe_choice_steps_have_no_reply():
    seen = replay()
    if "measurement" not in seen:
        return {"failed": seen}
    decided = [r for r in _records(seen) if isinstance(r.get("decision"), dict)]
    return {"decided_records": len(decided), "with_a_reply": sum(1 for r in decided if r.get("reply") is not None),
            "generated_with_text": sum(1 for r in _records(seen) if not r.get("decision") and (r.get("reply") or {}).get("text"))}


def expected_choice_steps_have_no_reply():
    # 10 choice steps (6 stances, 1 red line, 3 open points) and 3 audits decide; changes and wording generate.
    return {"decided_records": 13, "with_a_reply": 0, "generated_with_text": 4}


def neutralise_choice_steps_have_no_reply():
    return with_source(na, "run", 'reply=None if isinstance(result.get("decision"), dict) else text,', 'reply=text,')


def observe_held_step_written_when_a_call_raises():
    seen = replay(script={"raise_at": 3})
    if "measurement" not in seen:
        return {"failed": seen}
    steps = [r for r in seen["measurement"]["rows"] if r["form"] == na.STEP_FORM]
    return {"stopped": seen["code"] != 0, "complete": seen["measurement"]["complete"], "rows": len(steps),
            "records": len(_records(seen)), "every_row_recorded": all(r.get("call_id") for r in steps),
            "last_in_the_pass": len(seen["main"])}


def expected_held_step_written_when_a_call_raises():
    # The third choice call raises: changes, two stances (P-A1-1) asked before it, each written, the last in the
    # pass folder, and their rows in the measurement.
    return {"stopped": True, "complete": False, "rows": 3, "records": 3, "every_row_recorded": True, "last_in_the_pass": 1}


def neutralise_held_step_written_when_a_call_raises():
    return with_source(na, "run", "flush(pending.pop(), context)", "None")


def observe_refused_step_written_as_refused():
    seen = replay(script={"tie": True})
    if "measurement" not in seen:
        return {"failed": seen}
    refused = [r for r in _records(seen) if r.get("error_category") == na.REFUSED_CATEGORY]
    return {"refused": sorted((r["backend_ok"], r.get("error"), r.get("decision"), r.get("reply")) for r in refused),
            "rows": sorted(r.get("refused") for r in seen["measurement"]["rows"] if r.get("refused")),
            "pieces": "raised" if isinstance(seen["answers"], str) else _pieces(_row(seen))}


def expected_refused_step_written_as_refused():
    return {"refused": [(False, "method_refused: stance not_declared", None, None)] * 2,
            "rows": ["not_declared", "not_declared"], "pieces": expected_each_step_checked()["pieces"]}


def neutralise_refused_step_written_as_refused():
    return with_source(na, "run", 'held["error"] = refusal_error(entry)', 'pass')


def observe_reread_counts_stepwise_audits():
    seen = replay(script={"audit_tie": True})
    if "measurement" not in seen or isinstance(seen["again"], str):
        return {"failed": str(seen.get("again"))}
    row = next(r for r in seen["again"]["rows"] if r["group"] == "system_advice")
    return {"method": row.get("method"), "audit": row.get("audit"), "drops": row.get("drops")}


def expected_reread_counts_stepwise_audits():
    return {"method": "stepwise", "audit": {"P-A1-1": "supported", "P-A1-2": None, "P-A2-1": "supported"},
            "drops": {"audit": {"not_declared": 1}}}


def neutralise_reread_counts_stepwise_audits():
    import reread_replies as rr
    return with_source(rr, "advisor_rows",
                       "for d in (na.audit_prompts(config, p, text) if chain is None else na.audit_prompts(config, p, None, reply)):",
                       "for d in na.audit_prompts(config, p, text):")


# ---------------------------------------------------------------------------
# 516 one prompts file of several groups, read one group a candidate


CANDIDATES = (("base", "choice_direct"), ("reason_first", "choice_reason_first"), ("stepwise", "choice_stepwise"))


def _three_groups(folder, script=None):
    return rmc.a_pass(folder, script)


def _entry(seen, group):
    return {"steps": None, "group": group, "files": [(str(seen["out"]), str(seen["run"]))]}


def observe_split_by_group():
    import choice_read as cr
    with tempfile.TemporaryDirectory() as folder:
        seen = _three_groups(folder)
        asked = Counter(p["group"] for p in seen["value"]["prompts"] if p.get("form") == "choice")
        out = {"whole": caught(lambda: cr.load(cr.BASE, _entry(seen, None)) and "read")}
        for name, group in CANDIDATES:
            data = caught(lambda: cr.load(name, _entry(seen, group)))
            out[name] = data if isinstance(data, str) else {
                "rows_are_the_groups": len(data["rows"]) == asked[group],
                "models": sorted(m for i in data["identity"] for m in i["models"]), "group": data["identity"][0].get("group"),
                "dropped_groups": sorted(data["dropped"]), "decided": sum(r["decision"] is not None for r in data["rows"]) == asked[group]}
        out["wrong_method"] = caught(lambda: cr.load("stepwise", _entry(seen, "choice_reason_first")) and "read")
        out["parsed"] = {n: [e["group"] for e in v] for n, v in cr.parse_passes(
            ["base=P,R#choice_direct", "stepwise=P,R#choice_stepwise"]).items()}
    return out


def expected_split_by_group():
    out = {"whole": "raised ValueError", "wrong_method": "raised ValueError",
           "parsed": {"base": ["choice_direct"], "stepwise": ["choice_stepwise"]}}
    for name, group in CANDIDATES:
        out[name] = {"rows_are_the_groups": True, "models": [group], "group": group, "dropped_groups": [group], "decided": True}
    return out


def neutralise_split_by_group():
    import choice_read as cr
    return patch.object(cr, "pass_group", lambda name, value, group: None)


def observe_dropped_per_group():
    import choice_read as cr
    script = {"logits": lambda step: {"A": 1.0, "C": 1.0, "I": 0.0, "U": 0.0} if step == "comparison"
              else {"Y": 3.0, "N": 2.0, "U": 1.0}}
    with tempfile.TemporaryDirectory() as folder:
        seen = _three_groups(folder, script)
        out = {}
        for name, group in CANDIDATES:
            data = caught(lambda: cr.load(name, _entry(seen, group)))
            out[name] = data if isinstance(data, str) else {
                g: (d["prompts"], d["dropped"], sorted(d["by_reason"])) for g, d in data["dropped"].items()}
        stepwise = sum(1 for p in seen["value"]["prompts"] if p["group"] == "choice_stepwise")
        out["stepwise_prompts"] = stepwise
    return out


def expected_dropped_per_group():
    # The stepwise group's comparisons tie, so each of its prompts is dropped; the other two groups lose none.
    return {"base": {"choice_direct": (7, 0, [])}, "reason_first": {"choice_reason_first": (7, 0, [])},
            "stepwise": {"choice_stepwise": (7, 7, ["comparison:comparison_tie"])}, "stepwise_prompts": 7}


def neutralise_dropped_per_group():
    import choice_read as cr
    return with_source(cr, "load", 'measured += [r for r in seen.values() if group is None or r.get("group") == group]',
                       'measured += list(seen.values())')


def observe_method_binds_by_question():
    import choice_read as cr
    with tempfile.TemporaryDirectory() as folder:
        seen = _three_groups(folder)
        base = cr.load(cr.BASE, _entry(seen, "choice_direct"))
        method = cr.load("reason_first", _entry(seen, "choice_reason_first"))
        short = method["rows"][1:]
        doubled = method["rows"] + method["rows"][:1]
        return {"same": caught(lambda: cr.bound(base["rows"], method["rows"], by_question=True) or "bound"),
                "one_missing": caught(lambda: cr.bound(base["rows"], short, by_question=True) or "bound"),
                "one_twice": caught(lambda: cr.bound(base["rows"], doubled[1:] + doubled[:1], by_question=True) or "bound"),
                "by_prompt_id": caught(lambda: cr.bound(base["rows"], method["rows"]) or "bound")}


def expected_method_binds_by_question():
    # By prompt id the groups of one pass never bind (each group numbers its prompts apart); by question they do.
    return {"same": "bound", "one_missing": "raised ValueError", "one_twice": "raised ValueError",
            "by_prompt_id": "raised ValueError"}


def neutralise_method_binds_by_question():
    import choice_read as cr
    return with_source(cr, "bound", "if len(set(mine)) != len(mine) or sorted(mine) != sorted(theirs):", "if False:")


def observe_candidates_from_reasoning_methods():
    import choice_read as cr
    return {"candidates": list(cr.method_candidates()), "base": cr.candidate_method(cr.BASE),
            "stepwise": cr.candidate_method("stepwise"), "trained": cr.candidate_method(cr.DEV_MIX)}


def expected_candidates_from_reasoning_methods():
    import reasoning_methods as rm
    return {"candidates": [m for m in rm.METHODS if m != rm.DIRECT], "base": rm.DIRECT, "stepwise": rm.STEPWISE,
            "trained": rm.DIRECT}


def neutralise_candidates_from_reasoning_methods():
    import reasoning_methods as rm
    return patch.object(rm, "METHODS", (rm.DIRECT, rm.REASON_FIRST))


# ---------------------------------------------------------------------------
# 518 M-plain's advice allowance (D-725), a declared config value read when a prompt is built and loaded


def _config_with(folder, name, change):
    value = na.load_config()
    change(value)
    path = Path(folder) / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _allowances(config_path, groups=("b1", "system_advice")):
    with nb.setdir() as root, tempfile.TemporaryDirectory(prefix="allow_") as td:
        prompts = Path(td) / "prompts.json"
        na.build(root, "advice", list(groups), prompts, config_path=config_path(td) if callable(config_path) else config_path)
        loaded = caught(lambda: len(na.load_prompts(prompts)))
        value = json.loads(prompts.read_text(encoding="utf-8"))
        return {"by_group": sorted({(p["group"], p["max_new_tokens"]) for p in value["prompts"]}), "loaded": loaded}


def observe_mplain_allowance_declared():
    """The shipped config: the system's advice (plain) at 4,096, B1 at the form's 2,048, and the replay pass's
    reader and row carry the prompt's own figure."""
    out = _allowances(na.CONFIG_PATH)
    seen_readers, fake = [], nb.fake_reader

    def reader(group, allowance):
        seen_readers.append((group["group"], allowance))
        return fake(group, allowance)
    with patch.object(nb, "fake_reader", reader):
        seen = replay(method=None)
    out["pass_rows"] = None if "measurement" not in seen else sorted(
        {(r["group"], r["max_new_tokens"]) for r in seen["measurement"]["rows"] if r["form"] == "advice"})
    out["readers"] = sorted(set(seen_readers))
    return out


def expected_mplain_allowance_declared():
    return {"by_group": [("b1", 2048), ("system_advice", 4096)], "loaded": 2,
            "pass_rows": [("system_advice", 4096)], "readers": [("system_advice", 4096), ("system_audit", 8)]}


def neutralise_mplain_allowance_declared():
    return with_source(na, "advice_allowance", 'return block["max_new_tokens"]', 'return config["advice"]["max_new_tokens"]')


def observe_allowance_read_from_config():
    """Another declared figure is the prompt's figure (nothing typed in code); stepwise and reason_first keep the
    form's own figure; a figure that is not a positive integer is refused."""
    def set_plain(n):
        return lambda td: _config_with(td, "c.json", lambda v: v["advice"]["methods"].__setitem__("plain", {"max_new_tokens": n}))

    def method(m):
        return lambda td: _config_with(td, "c.json", lambda v: [g.__setitem__("method", m) for g in v["models"]
                                                                if g["group"] == "system_advice"])

    def bad(td):
        _config_with(td, "c.json", lambda v: v["advice"]["methods"].__setitem__("plain", {"max_new_tokens": 0}))
        return caught(lambda: na.load_config(Path(td) / "c.json") and "loaded")
    with tempfile.TemporaryDirectory(prefix="allowb_") as td:
        refused = bad(td)
    return {"declared_3000": _allowances(set_plain(3000), ("system_advice",))["by_group"],
            "reason_first": _allowances(method("reason_first"), ("system_advice",))["by_group"],
            "stepwise": _allowances(method("stepwise"), ("system_advice",))["by_group"],
            "zero_refused": refused}


def expected_allowance_read_from_config():
    return {"declared_3000": [("system_advice", 3000)], "reason_first": [("system_advice", 4096)],
            "stepwise": [("system_advice", 2048)], "zero_refused": "raised ValueError"}


def neutralise_allowance_read_from_config():
    return with_source(na, "advice_allowance", "if group == METHOD_GROUP and method in ALLOWANCE_METHODS:",
                       "if True:")


def observe_load_holds_the_allowance():
    """A prompts file whose system advice carries another allowance than its config declares is refused."""
    with nb.setdir() as root, tempfile.TemporaryDirectory(prefix="allowc_") as td:
        prompts = Path(td) / "prompts.json"
        na.build(root, "advice", ["system_advice"], prompts)
        value = json.loads(prompts.read_text(encoding="utf-8"))
        for p in value["prompts"]:
            p["max_new_tokens"] = 2048
        prompts.write_text(json.dumps(value), encoding="utf-8")
        return {"tampered": caught(lambda: len(na.load_prompts(prompts)))}


def expected_load_holds_the_allowance():
    return {"tampered": "raised ValueError"}


def neutralise_load_holds_the_allowance():
    return with_source(na, "load_prompts", '"max_new_tokens": (advice_allowance(config, p["group"]) if p["form"] == "advice"',
                       '"max_new_tokens": (p.get("max_new_tokens") if p["form"] == "advice"')


def observe_config_refuses_a_bad_allowance():
    """check_config's own guard: a plain or reason_first allowance that is not a positive integer is refused, at
    config load and in a prompts file's own config."""
    out = {}
    for method, value in (("plain", 0), ("plain", "4096"), ("reason_first", -1)):
        raw = na.load_config()
        raw["advice"]["methods"][method] = dict(raw["advice"]["methods"][method], max_new_tokens=value)
        out["%s=%r" % (method, value)] = caught(lambda: na.check_config(raw) and "loaded")
    return out


def expected_config_refuses_a_bad_allowance():
    return {"plain=0": "raised ValueError", "plain='4096'": "raised ValueError", "reason_first=-1": "raised ValueError"}


def neutralise_config_refuses_a_bad_allowance():
    return with_source(na, "check_config",
                       'raise ValueError("the %s method declares a positive max_new_tokens (D-725, D-740)" % method)',
                       "pass")


def observe_reason_first_allowance_equal():
    """D-740: reason_first's advice takes advice.methods.reason_first.max_new_tokens (4,096, equal to M-plain's),
    another declared figure is its figure, an undeclared one falls back to the form's; stepwise keeps the form's
    figure for its advice prompt and its own per-step 512."""
    def method(m, change=None):
        def make(td):
            def edit(v):
                for g in v["models"]:
                    if g["group"] == "system_advice":
                        g["method"] = m
                if change:
                    change(v)
            return _config_with(td, "c.json", edit)
        return make
    drop = lambda v: v["advice"]["methods"]["reason_first"].pop("max_new_tokens")
    three = lambda v: v["advice"]["methods"]["reason_first"].__setitem__("max_new_tokens", 3000)
    return {"reason_first": _allowances(method("reason_first"), ("system_advice",))["by_group"],
            "plain": _allowances(method("plain"), ("system_advice",))["by_group"],
            "reason_first_3000": _allowances(method("reason_first", three), ("system_advice",))["by_group"],
            "reason_first_undeclared": _allowances(method("reason_first", drop), ("system_advice",))["by_group"],
            "stepwise": _allowances(method("stepwise"), ("system_advice",))["by_group"],
            "stepwise_step": na.load_config()["advice"]["methods"]["stepwise"]["max_new_tokens"]}


def expected_reason_first_allowance_equal():
    return {"reason_first": [("system_advice", 4096)], "plain": [("system_advice", 4096)],
            "reason_first_3000": [("system_advice", 3000)], "reason_first_undeclared": [("system_advice", 2048)],
            "stepwise": [("system_advice", 2048)], "stepwise_step": 512}


def neutralise_reason_first_allowance_equal():
    return patch.object(na, "ALLOWANCE_METHODS", (na.PLAIN,))


def _cap_run(changes):
    seen = replay(script={"changes": changes})
    if "measurement" not in seen or isinstance(seen["answers"], str):
        return {"failed": str(seen.get("replay") or seen.get("answers"))}
    records = _records(seen)
    row = _row(seen)
    again = seen["again"]
    again = again if isinstance(again, str) else next(r for r in again["rows"] if r["group"] == "system_advice")
    steps = [r for r in seen["measurement"]["rows"] if r["form"] == na.STEP_FORM and r["step"] == "changes"]
    return {"categories": sorted({r.get("error_category") for r in records if r.get("error_category")}),
            "errors": sorted({r["error"] for r in records if r.get("error")}),
            "cap_rows": sum(1 for r in steps if r.get("cap_reached")), "refused": row.get("steps_refused"),
            "reread_same": not isinstance(again, str) and again.get("steps_refused") == row.get("steps_refused")}


BAD_LINE = "zzz yyy xxx www vvv uuu"


def observe_cap_step_has_its_own_reason():
    return {"capped_refused": _cap_run((BAD_LINE, "cap")), "short_refused": _cap_run((BAD_LINE, 7))}


def expected_cap_step_has_its_own_reason():
    # Three changes steps a run. Capped and refused: its own category and reason, counted by reason, read again the
    # same. Refused short of the cap: the form reason as before.
    return {"capped_refused": {"categories": ["step_cap_reached"], "errors": ["step_cap_reached: changes"], "cap_rows": 3,
                               "refused": {"changes:step_cap_reached": 3}, "reread_same": True},
            "short_refused": {"categories": ["method_refused"], "errors": ["method_refused: changes not_in_the_proposal"],
                              "cap_rows": 0, "refused": {"changes:not_in_the_proposal": 3}, "reread_same": True}}


def neutralise_cap_step_has_its_own_reason():
    sp = " " * 28
    return with_source(na, "run", 'if row.get("cap_reached"):\n' + sp + 'entry["refused"] = CAP_REASON',
                       'if False:\n' + sp + 'pass')


GROUPS = {
    "708": ("cap_step_has_its_own_reason",),
    "518": ("mplain_allowance_declared", "allowance_read_from_config", "load_holds_the_allowance",
            "config_refuses_a_bad_allowance", "reason_first_allowance_equal"),
    "515": ("chain_on_the_replay_pass", "each_step_checked", "off_unless_declared", "recomposed_from_saved_steps",
            "choice_steps_have_no_reply", "held_step_written_when_a_call_raises", "refused_step_written_as_refused",
            "reread_counts_stepwise_audits"),
    "516": ("split_by_group", "dropped_per_group", "method_binds_by_question", "candidates_from_reasoning_methods"),
}
WHAT = {"708": "a generated step that stopped at its token cap is recorded and counted under its own reason, step_cap_reached, never as a form refusal",
        "515": "the negotiation advisor's step-wise chain on the replay pass, each step checked by Python, one "
               "record a step, the reply composed again from the saved steps, off unless declared",
        "516": "one prompts file of three groups read one group a candidate, bound by question, a dropped figure each",
        "518": "M-plain's advice allowance (D-725) and reason_first's equal one (D-740) read from the config's "
               "advice.methods when a prompt is built and loaded, B1 and stepwise at the form's figure, a bad or "
               "tampered allowance refused"}


def run_group(number):
    done = []
    for name in GROUPS[number]:
        space = globals()
        observe, expected, neutralise = space["observe_" + name], space["expected_" + name], space["neutralise_" + name]
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                first = observe()
                with neutralise():
                    broken = caught(observe)
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
    return "PASS", "%d proofs, each neutralise, fail, restore, pass, no model: %s (%s)" % (len(done), WHAT[number], ", ".join(done))


if __name__ == "__main__":
    status, detail = run_group(sys.argv[1] if len(sys.argv) > 1 else "515")
    print(status, detail)
    raise SystemExit(0 if status == "PASS" else 1)
