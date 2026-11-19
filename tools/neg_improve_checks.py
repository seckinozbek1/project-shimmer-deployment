#!/usr/bin/env python3
"""Checks 531 to 533 (lane/neg-improve, D-756): the negotiation improvements Seckin approved at 20:35 and 20:36.

531, D-756 items 5 and 6 and the margins of item 3 (benchmark/baselines/neg_advisor.py): N3, the stepwise chain's
    declared order `choice_first` asks every choice step of a proposal (stance per touched position, red line,
    open point) before any generated step (changes, wording), and a refused generated step drops only its own
    field, counted, never ending the chain (the shipped `generated_first` order unchanged and the default); P8,
    the stance step's context `full` or `trimmed` chosen per prompt at build time, both arms side by side in one
    prompts file, each prompt, reply and answers row marked, never a silent swap, a scorer reading one arm;
    each choice step's per-answer probabilities saved in its reply record (CHOICE-A) and carried, with the
    oppose margin, into the composed reply's `position_stances`.
532, D-756 item 3 (P3, tools/score_neg_advisor.py): a proposal's conflict decided by one declared threshold on
    the largest oppose margin among the persona's positions on it (config/neg_advisor_dev.json, null until tuned,
    read at call time), the figure reported with and without it; the tuning helper picks the threshold on a split
    of item ids and refuses a split that overlaps the deciding set.
533, D-756 item 2 (N1, tools/score_neg_advisor.py): oppose recall and precision over all positions against the
    build's stances, item-clustered BCa intervals, a pair the chain did not judge a miss, beside the bar and
    never inside it.
535, D-758 (tools/score_neg_advisor.py link_article_positions): the system's composition step links an
    article-level position to the single proposal under its article, from structure alone, off by default.

No model, no key, no real item, nothing launched: fake backends on the invented fixtures of
tools/neg_advisor_checks.py, in temporary folders. Every proof is run as built (passes), neutralised (must fail),
restored and run again (passes).
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
import replay_methods_checks as rpm  # noqa: E402
import reply_records  # noqa: E402
import reread_replies as rr  # noqa: E402
import score_neg_advisor as sc  # noqa: E402

caught, with_source = rmc.caught, rmc.with_source
BAD_CHANGES = "a line that the proposal does not hold anywhere"
BAD_WORDING = "Reporting as in PAR-1 with a longer period"


# ---------------------------------------------------------------------------
# fixtures


class ArmBackend(rpm.StepBackend):
    """The step-wise fake model of check 515, reading a stance question's position from the line after "A
    position on record by" (a trimmed question also shows the persona's red lines), and, when `bad` is set,
    giving a `changes` line the proposal does not hold and a counter wording that cites an id."""
    script = {}

    def generate(self, system, user, n):
        if self.script.get("bad") and "What does this proposal change?" in user:
            return {"text": BAD_CHANGES, "payload": user, "form": "rendered_prompt"}
        if self.script.get("bad") and "Write one middle-ground wording" in user:
            return {"text": BAD_WORDING, "payload": user, "form": "rendered_prompt"}
        return super().generate(system, user, n)

    def choose(self, system, user, answers):
        if {a["label"] for a in answers} == set(na.POSITION_STANCES) and "A position on record by" in user:
            said = user.split("A position on record by", 1)[1]
            wanted = next(p["stance"] for p in nb.BUILD["positions"] if p["quote"] in said)
            rows = [{"label": a["label"], "surface": a["surface"], "token_id": k,
                     "probability": 0.9 if a["label"] == wanted else 0.1 / (len(answers) - 1)}
                    for k, a in enumerate(answers)]
            return {"decision": {"schema": "choice-decision-v1", "answers": rows, "declared_mass": 1.0},
                    "payload": user, "form": "rendered_prompt"}
        return super().choose(system, user, answers)


def _config(folder, order=None, drop_trimmed=False):
    value = na.load_config()
    for g in value["models"]:
        if g["group"] == "system_advice":
            g["method"] = na.STEPWISE
    block = value["advice"]["methods"][na.STEPWISE]
    if order is not None:
        block["order"] = order
    if drop_trimmed:
        block.pop("stance_trimmed", None)
    path = Path(folder) / "config_neg_improve.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def replay(order=None, contexts=None, script=None, builds=(nb.BUILD,)):
    """The fixture item's stepwise system advice under `order`, built once per stance arm in `contexts`, run
    through replay_prompts.py's own `run`, then read by neg_advisor.answers and the re-reader."""
    import replay_prompts
    with nb.setdir(builds=builds) as root, tempfile.TemporaryDirectory(prefix="negimp_") as td:
        prompts = Path(td) / "prompts.json"
        na.build(root, "advice", ["system_advice"], prompts, config_path=_config(td, order), stance_contexts=contexts)
        out = Path(td) / "pass"
        backend = type("Scripted", (ArmBackend,), {"script": dict(script or {})})
        with patch.object(na, "make_advisor_backend", backend), patch.object(na, "reader_of", nb.fake_reader), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = replay_prompts.main(["run", "--prompts", str(prompts), "--out", str(out), "--paths", "sdpa"])
        if not (out / na.MEASUREMENT_FILE).is_file():
            return {"replay": code}
        measurement = json.loads((out / na.MEASUREMENT_FILE).read_text(encoding="utf-8"))
        side_dir = out / na.STEPWISE_DIR / "audit" / "model_replies"
        records = reply_records.records(out / "audit" / "model_replies") + \
            (reply_records.records(side_dir) if side_dir.is_dir() else [])
        return {"measurement": measurement, "records": records, "value": json.loads(prompts.read_text(encoding="utf-8")),
                "answers": caught(lambda: na.answers(prompts, out)), "again": caught(lambda: rr.advisor_answers(prompts, out)),
                "code": code}


def _system_rows(answers):
    return [r for r in answers["rows"] if r["group"] == "system_advice"]


def _pieces(row):
    reply = row.get("reply") or {}
    return {pid: (e.get("conflict"), e.get("stance"), bool(e.get("wording")), bool(e.get("changes")))
            for pid, e in sorted((reply.get("proposals") or {}).items())}


def _asked(seen):
    return [r["step"] for r in seen["measurement"]["rows"] if r["form"] == na.STEP_FORM]


# ---------------------------------------------------------------------------
# 531 N3, P8 and the saved margins


def observe_choice_steps_first():
    out = {}
    for order in (None, na.CHOICE_FIRST):
        seen = replay(order=order)
        if "measurement" not in seen or isinstance(seen["answers"], str):
            return {"failed": str(seen.get("replay") or seen.get("answers"))}
        row = _system_rows(seen["answers"])[0]
        out[str(order)] = {"asked": _asked(seen), "pieces": _pieces(row), "refused": row.get("steps_refused")}
    return out


def expected_choice_steps_first():
    pieces = {"P-A1-1": ("no_conflict", "accept", False, True), "P-A1-2": ("not_stated", "counter", True, True),
              "P-A2-1": ("conflict", "reject", False, True)}
    return {"None": {"asked": ["changes", "stance", "stance", "stance", "open_point",
                               "changes", "open_point", "wording",
                               "changes", "stance", "stance", "stance", "red_line", "open_point"],
                     "pieces": pieces, "refused": {}},
            "choice_first": {"asked": ["stance", "stance", "stance", "open_point", "changes",
                                       "open_point", "changes", "wording",
                                       "stance", "stance", "stance", "red_line", "open_point", "changes"],
                             "pieces": pieces, "refused": {}}}


def neutralise_choice_steps_first():
    return patch.object(na, "step_order", lambda block: na.GENERATED_FIRST)


def observe_refused_generated_drops_its_field():
    out = {}
    for order in (None, na.CHOICE_FIRST):
        seen = replay(order=order, script={"bad": True})
        if "measurement" not in seen or isinstance(seen["answers"], str):
            return {"failed": str(seen.get("replay") or seen.get("answers"))}
        row = _system_rows(seen["answers"])[0]
        again = _system_rows(seen["again"])[0] if not isinstance(seen["again"], str) else {}
        out[str(order)] = {"pieces": _pieces(row), "refused": row.get("steps_refused"),
                           "reread_steps": (again.get("steps_refused"), (again.get("drops") or {}).get("steps")), "audits": seen["measurement"]["derived"]}
    return out


def expected_refused_generated_drops_its_field():
    # generated_first: a refused changes line ends each proposal's chain before any stance (the drop loss N3
    # removes); choice_first: every stance, conflict and open point stands, only `changes` and the counter's
    # `wording` are missing, each refusal counted by step and reason, and every piece is audited.
    return {"None": {"pieces": {"P-A1-1": (None, None, False, False), "P-A1-2": (None, None, False, False),
                                "P-A2-1": (None, None, False, False)},
                     "refused": {"changes:not_in_the_proposal": 3},
                     "reread_steps": ({"changes:not_in_the_proposal": 3}, {"step_refused": 3}), "audits": 0},
            "choice_first": {"pieces": {"P-A1-1": ("no_conflict", "accept", False, False),
                                        "P-A1-2": ("not_stated", "counter", False, False),
                                        "P-A2-1": ("conflict", "reject", False, False)},
                             "refused": {"changes:not_in_the_proposal": 3, "wording:cites_an_id": 1},
                             "reread_steps": ({"changes:not_in_the_proposal": 3, "wording:cites_an_id": 1}, {"step_refused": 4}),
                             "audits": 3}}


def neutralise_refused_generated_drops_its_field():
    return with_source(na, "stepwise_advice", 'if not why:\n                    piece["changes"] = value',
                       'if why:\n                    piece.clear()\n                    continue\n'
                       '                piece["changes"] = value')


def _stance_payloads(seen, arm):
    pid = {p["prompt_id"]: p.get("stance_context") for p in seen["value"]["prompts"]}
    rows = {r["call_id"]: r for r in seen["measurement"]["rows"] if r.get("form") == na.STEP_FORM}
    out = []
    for rec in seen["records"]:
        row = rows.get(rec.get("call_id"))
        if row and row["step"] == "stance" and pid.get(row["derived_from"]) == arm:
            payload = rec.get("payload") or {}
            out.append(payload.get("text") or "" if isinstance(payload, dict) else str(payload))
    return out


def observe_stance_arms_side_by_side():
    seen = replay(contexts=["full", "trimmed"], builds=(nb.BUILD, nb.GAME))
    if "measurement" not in seen or isinstance(seen["answers"], str):
        return {"failed": str(seen.get("replay") or seen.get("answers"))}
    full, trimmed = _stance_payloads(seen, "full"), _stance_payloads(seen, "trimmed")
    rows = [r for r in _system_rows(seen["answers"]) if r["item_id"] == nb.BUILD["item_id"]]
    again = [] if isinstance(seen["again"], str) else _system_rows(seen["again"])
    with nb.setdir() as root, tempfile.TemporaryDirectory(prefix="negimp_") as td:
        refusals = {
            "b1_marked": caught(lambda: na.build(root, "advice", ["b1"], Path(td) / "a.json",
                                                 config_path=_config(td), stance_contexts=["trimmed"])),
            "trimmed_undeclared": caught(lambda: na.build(root, "advice", ["system_advice"], Path(td) / "b.json",
                                                          config_path=_config(td, drop_trimmed=True),
                                                          stance_contexts=["full", "trimmed"])),
            "arm_twice": caught(lambda: na.build(root, "advice", ["system_advice"], Path(td) / "c.json",
                                                 config_path=_config(td), stance_contexts=["full", "full"]))}
    unmarked = dict(seen["answers"], rows=[r for r in seen["answers"]["rows"]])
    return {"prompts": sorted(str(p.get("stance_context")) for p in seen["value"]["prompts"]),
            "answer_arms": sorted(str(r.get("stance_context")) for r in _system_rows(seen["answers"])),
            "reread_arms": sorted(str(r.get("stance_context")) for r in again),
            "pieces_per_arm": sorted(str(_pieces(r)) for r in rows) == [str(_pieces(rows[0]))] * 2,
            "full_questions": (len(full), all("in article" in u and "red lines on record" not in u for u in full)),
            "trimmed_questions": (len(trimmed), all("The red lines on record of the party you advise:\n- We cannot accept "
                                                    "mandatory contributions." in u and "in article" not in u
                                                    for u in trimmed)),
            "one_arm_needed": caught(lambda: sc.replies_by_item(unmarked, "system_advice")),
            "trimmed_read": sorted(sc.replies_by_item(unmarked, "system_advice", "trimmed")),
            "selected": len(sc.select_arm(unmarked, "full")["rows"]),
            "refusals": refusals}


def expected_stance_arms_side_by_side():
    # The game item asks no stance: one prompt, unmarked (read as the full arm), never two.
    return {"prompts": ["None", "full", "trimmed"], "answer_arms": ["None", "full", "trimmed"],
            "reread_arms": ["None", "full", "trimmed"],
            "pieces_per_arm": True, "full_questions": (6, True), "trimmed_questions": (6, True),
            "one_arm_needed": "raised ValueError", "trimmed_read": ["fx-k2-alpha"], "selected": 2,
            "refusals": {"b1_marked": "raised ValueError", "trimmed_undeclared": "raised ValueError",
                         "arm_twice": "raised ValueError"}}


def neutralise_stance_arms_side_by_side():
    # The silent swap the rule forbids: the pass asks every arm in the full context.
    return with_source(na, "stepwise_call", 'stance_context=prompt.get("stance_context"))', 'stance_context=None)')


def _margins(row):
    out = {}
    for pid, piece in sorted(((row.get("reply") or {}).get("proposals") or {}).items()):
        kept = piece.get("position_stances")
        if kept:
            out[pid] = {k: (v["stance"], None if v["oppose_margin"] is None else round(v["oppose_margin"], 6))
                        for k, v in sorted(kept.items())}
    return out


def observe_choice_margins_saved():
    seen = replay()
    if "measurement" not in seen or isinstance(seen["answers"], str) or isinstance(seen["again"], str):
        return {"failed": str(seen.get("replay") or seen.get("answers") or seen.get("again"))}
    steps = {r["call_id"]: r["step"] for r in seen["measurement"]["rows"] if r.get("form") == na.STEP_FORM}
    choice = [r for r in seen["records"] if steps.get(r.get("call_id")) in na.STEP_ANSWERS]
    return {"choice_records": len(choice),
            "with_probabilities": sum(1 for r in choice if isinstance(r.get("decision"), dict) and
                                      abs(sum(a["probability"] for a in r["decision"]["answers"]) - 1) < 1e-9),
            "one_record_a_step": len(steps) == len({r.get("call_id") for r in seen["records"]} & set(steps)),
            "margins": _margins(_system_rows(seen["answers"])[0]),
            "reread_same": _margins(_system_rows(seen["again"])[0]) == _margins(_system_rows(seen["answers"])[0])}


def expected_choice_margins_saved():
    m = round(0.9 - 0.05, 6)
    return {"choice_records": 10, "with_probabilities": 10, "one_record_a_step": True,
            "margins": {"P-A1-1": {"POS-1": ("support", -m), "POS-3": ("support", -m), "POS-5": ("oppose", m)},
                        "P-A2-1": {"POS-2": ("oppose", m), "POS-4": ("oppose", m), "POS-6": ("support", -m)}},
            "reread_same": True}


def neutralise_choice_margins_saved():
    return with_source(na, "recompose_stepwise",
                       'decision_probabilities(record.get("decision") if record.get("backend_ok") else None)', 'None')


# ---------------------------------------------------------------------------
# 532 P3 and 533 N1, on answers files written here (the scorer's side; no model)


def _builds(n=5):
    out = []
    for k in range(n):
        b = copy.deepcopy(nb.BUILD)
        b["item_id"] = "fx-k2-%s" % "abcdefgh"[k]
        out.append(b)
    return out


def _stance(party, stance, margin):
    p = {"oppose": 0.5 + margin / 2, "other": 0.5 - margin / 2} if margin is not None else None
    probs = None if p is None else {"oppose": p["oppose"], "support": p["other"], "accept": 0.0}
    return {"party": party, "stance": stance, "probabilities": probs, "oppose_margin": margin}


def _answers(items, *, unjudged=(), persona_margin=-0.2, arm=None):
    """A re-reader's answers file: each item's system reply misses the conflict on P-A2-1 (the persona's POS-2 read
    accept at `persona_margin`), with every checked stance and its margin; an item in `unjudged` has no stance on
    P-A2-1 at all."""
    rows = []
    for item_id, item in sorted(items.items()):
        reply = nb.reply_of(item)
        props = reply["proposals"]
        props["P-A2-1"] = dict(props["P-A2-1"], conflict="no_conflict", stance="accept", wording=None)
        props["P-A2-1"].pop("wording")
        props["P-A1-1"]["position_stances"] = {"POS-1": _stance("ALPHA", "support", -0.9),
                                               "POS-3": _stance("BETA", "support", -0.8),
                                               "POS-5": _stance("GROUP1", "oppose", 0.85)}
        if item_id not in unjudged:
            props["P-A2-1"]["position_stances"] = {"POS-2": _stance("ALPHA", "accept", persona_margin),
                                                   "POS-4": _stance("BETA", "oppose", 0.7),
                                                   "POS-6": _stance("GROUP1", "oppose", 0.1)}
            props["P-A2-1"]["red_line_hit"] = False
        row = {"prompt_id": "a-" + item_id, "group": "system_advice", "form": "advice", "item_id": item_id,
               "reply": reply, "audit": {}, "drops": {}}
        if arm is not None:
            row["stance_context"] = arm
        rows.append(row)
    return {"schema": rr.ADVISOR_SCHEMA, "read_by": "fixture", "rows": rows}


@contextlib.contextmanager
def _set(n=5):
    with nb.setdir(builds=_builds(n)) as root:
        yield root, na.read_items(root), sc.read_keys(root)


def _est(block, name):
    v = block.get(name) or {}
    return None if v.get("estimate") is None else round(v["estimate"], 6)


def observe_threshold_on_the_largest_margin():
    with _set(1) as (_root, items, _keys):
        item = items["fx-k2-a"]
        reply = _answers(items)["rows"][0]["reply"]
        out = {}
        for t in (None, -0.3, -0.1):
            got, counts = sc.margin_conflict_reply(item, reply, t)
            out[str(t)] = ({pid: (e.get("conflict"), e.get("stance")) for pid, e in sorted(got["proposals"].items())},
                           dict(counts))
        return out


def expected_threshold_on_the_largest_margin():
    # Only the persona's margin decides: GROUP1's 0.85 oppose on P-A1-1 and BETA's 0.7 on P-A2-1 never do.
    same = {"P-A1-1": ("no_conflict", "accept"), "P-A1-2": ("not_stated", "reject"), "P-A2-1": ("no_conflict", "accept")}
    return {"None": (same, {}),
            "-0.3": (dict(same, **{"P-A2-1": ("conflict", "reject")}), {"decided": 2, "moved_to_conflict": 1}),
            "-0.1": (same, {"decided": 2})}


def neutralise_threshold_on_the_largest_margin():
    return with_source(sc, "margin_conflict_reply", 'if v.get("party") == persona]', 'if True]')


def _dev_config(folder, threshold):
    value = json.loads(sc.DEV_CONFIG.read_text(encoding="utf-8"))
    value["conflict_margin_threshold"] = threshold
    path = Path(folder) / "neg_advisor_dev.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def observe_reported_with_and_without():
    with _set() as (root, items, _keys), tempfile.TemporaryDirectory(prefix="negimp_") as td:
        answers = _answers(items)
        out = {"shipped_null": sc.dev_config()["conflict_margin_threshold"]}
        for t in (None, -0.3):
            p3 = sc.dev_figures(root, answers, config_path=_dev_config(td, t), resamples=200)["P3"]["real"]
            out[str(t)] = {"without": (_est(p3["without"], "conflict_f1"), _est(p3["without"], "M1")),
                           "with": p3["with"] if isinstance(p3["with"], str) else
                           (_est(p3["with"], "conflict_f1"), _est(p3["with"], "M1"), p3["with"]["proposals"])}
        out["refused_unread"] = caught(lambda: sc.dev_figures(root, dict(answers, schema="other"),
                                                              config_path=_dev_config(td, -0.3), resamples=50))
        return out


def expected_reported_with_and_without():
    return {"shipped_null": None,
            "None": {"without": (0.0, 0.555556), "with": "no threshold declared (config/neg_advisor_dev.json)"},
            "-0.3": {"without": (0.0, 0.555556), "with": (1.0, 1.0, {"decided": 10, "moved_to_conflict": 5})},
            "refused_unread": "raised ValueError"}


def neutralise_reported_with_and_without():
    return patch.object(sc, "margin_conflict_reply", lambda item, reply, threshold: (reply, Counter()))


def _split(folder, name, ids):
    path = Path(folder) / name
    path.write_text(json.dumps({"schema": sc.SPLIT_SCHEMA, "items": ids}), encoding="utf-8")
    return sc.read_split(path)


def observe_tuned_off_the_deciding_set():
    with _set() as (_root, items, keys), tempfile.TemporaryDirectory(prefix="negimp_") as td:
        answers = _answers(items)
        split = _split(td, "split.json", ["fx-k2-a", "fx-k2-b", "fx-k2-c"])
        deciding = _split(td, "deciding.json", ["fx-k2-d", "fx-k2-e"])
        tuned = sc.tune_threshold(items, keys, answers, split, deciding)
        return {"tuned": {k: tuned[k] for k in ("threshold", "conflict_f1_on_split", "split_items", "candidates",
                                                "deciding_items", "overlap")},
                "overlap": caught(lambda: sc.tune_threshold(items, keys, answers, split,
                                                            _split(td, "d2.json", ["fx-k2-c", "fx-k2-d"]))),
                "unknown_item": caught(lambda: sc.tune_threshold(items, keys, answers,
                                                                 _split(td, "s2.json", ["fx-k2-z"]), deciding)),
                "repeated_id": caught(lambda: _split(td, "s3.json", ["fx-k2-a", "fx-k2-a"]))}


def expected_tuned_off_the_deciding_set():
    # Candidates are the persona's largest margins on the split: -0.9 (P-A1-1) flags a false conflict, -0.2
    # (P-A2-1) finds the three conflicts alone.
    return {"tuned": {"threshold": -0.2, "conflict_f1_on_split": 1.0, "split_items": 3, "candidates": 2,
                      "deciding_items": 2, "overlap": 0},
            "overlap": "raised ValueError", "unknown_item": "raised ValueError", "repeated_id": "raised ValueError"}


def neutralise_tuned_off_the_deciding_set():
    return with_source(sc, "tune_threshold", "if overlap:", "if False:")


def observe_oppose_recall_and_precision():
    with _set() as (root, items, keys):
        answers = _answers(items, unjudged=("fx-k2-e",))
        rep = sc.position_oppose_report(items, keys, sc.build_positions(root), answers, resamples=200)
        real = rep["real"]
        return {"counts": {k: real[k] for k in ("items", "units", "judged", "true_oppose", "predicted_oppose")},
                "recall": _est(real, "recall"), "precision": _est(real, "precision"),
                "bounded": all(real[f]["lower"] <= real[f]["estimate"] <= real[f]["upper"] for f in ("recall", "precision")),
                "status": rep["status"], "outside_the_bar": "N1" not in sc.BAR_FIGURES and
                not any(f == "N1" for _line, figs in sc.NEG_BAR_LINES for f, _v in figs),
                "synthetic_apart": rep["synthetic"]["items"]}


def expected_oppose_recall_and_precision():
    # Four items: POS-5 and POS-4 found, POS-2 missed, POS-6 a false oppose; the fifth has no stance on P-A2-1, so
    # its two oppose positions there are misses and nothing is predicted: tp 9, fn 6, fp 4.
    return {"counts": {"items": 5, "units": 30, "judged": 27, "true_oppose": 15, "predicted_oppose": 13},
            "recall": 0.6, "precision": round(9 / 13, 6), "bounded": True, "status": sc.DEV_STATUS,
            "outside_the_bar": True, "synthetic_apart": 0}


def neutralise_oppose_recall_and_precision():
    return with_source(sc, "oppose_part", 'c["fn"] += true and said != OPPOSE_STANCE',
                       'c["fn"] += true and said is not None and said != OPPOSE_STANCE')


def observe_clustered_by_item():
    with _set() as (root, items, keys):
        rep = sc.position_oppose_report(items, keys, sc.build_positions(root), _answers(items, arm="trimmed"),
                                        stance_context="trimmed", resamples=200)
        r = rep["real"]["recall"]
        return {"estimate": round(r["estimate"], 6), "width": round(r["upper"] - r["lower"], 9), "items": r["items"],
                "arm": rep["stance_context"]}


def expected_clustered_by_item():
    # Five identical items: resampling items cannot move the figure, so the interval has no width; resampling
    # positions would.
    return {"estimate": round(2 / 3, 6), "width": 0.0, "items": 5, "arm": "trimmed"}


def neutralise_clustered_by_item():
    return with_source(sc, "position_oppose_report",
                       'parts.append(oppose_part(linked_item(items[i], article_link), truth, (rows.get(i) or {}).get("reply")))',
                       'parts.extend(Counter({k: 1}) for k, v in oppose_part(linked_item(items[i], article_link), truth, '
                       '(rows.get(i) or {}).get("reply")).items() if k in ("tp", "fn", "fp") for _ in range(v))')


# ---------------------------------------------------------------------------
# 535 D-758: the composition step's article-to-proposal link


def _link_item():
    """The fixture item with four more article-level positions, one per refusal: POS-7 on A1 (two proposals),
    POS-8 with no article, POS-9 on A9 (outside the excerpt), POS-10 on A3 (no proposal)."""
    with _set(1) as (_root, items, _keys):
        item = copy.deepcopy(items["fx-k2-a"])
    extra = [("POS-7", "A1"), ("POS-8", None), ("POS-9", "A9"), ("POS-10", "A3")]
    for pid, aid in extra:
        item["positions"].append({"id": pid, "party": "BETA", "round": 2, "article": aid, "proposal": None,
                                  "quote": "fixture %s" % pid, "source": "fixture"})
    return item


def _link_view(item):
    before = copy.deepcopy(item)
    out, record = sc.link_article_positions(item)
    return {"positions": {p["id"]: (p["article"], p["proposal"], p.get("linked_from")) for p in out["positions"]},
            "linked": record["linked"], "refused": record["refused"],
            "counts": {k: v for k, v in record["counts"].items() if v}, "item_unchanged": item == before}


def observe_single_proposal_linked():
    v = _link_view(_link_item())
    return {"positions": {k: v["positions"][k] for k in ("POS-1", "POS-2", "POS-4", "POS-6")},
            "linked": v["linked"], "item_unchanged": v["item_unchanged"]}


def expected_single_proposal_linked():
    # A2 holds one proposal, P-A2-1: its three article-level positions (the persona's oppose POS-2 among them)
    # are put on it; POS-1, already on A1 proposal 1, is left as it is.
    return {"positions": {"POS-1": ("A1", 1, None), "POS-2": ("A2", 1, "article"), "POS-4": ("A2", 1, "article"),
                          "POS-6": ("A2", 1, "article")},
            "linked": [{"position": p, "article": "A2", "proposal": "P-A2-1"} for p in ("POS-2", "POS-4", "POS-6")],
            "item_unchanged": True}


def neutralise_single_proposal_linked():
    return with_source(sc, "link_article_positions", 'why = None if n == 1 else', 'why = "no_proposal" if n == 0 else')


def observe_several_proposals_not_linked():
    item = _link_item()
    v = _link_view(item)
    out, _r = sc.link_article_positions(item)
    # The plan's fallback still applies POS-7 to each A1 proposal where BETA holds no proposal-level position.
    return {"POS-7": v["positions"]["POS-7"],
            "refused": [r for r in v["refused"] if r["position"] == "POS-7"],
            "applies_to": [n for n in (1, 2) if "POS-7" in {p["id"] for p in sc.applicable(out["positions"], "BETA", "A1", n)}]}


def expected_several_proposals_not_linked():
    return {"POS-7": ("A1", None, None),
            "refused": [{"position": "POS-7", "article": "A1", "reason": "several_proposals"}], "applies_to": [2]}


def neutralise_several_proposals_not_linked():
    return with_source(sc, "link_article_positions", '"no_proposal" if n == 0 else "several_proposals"',
                       '"no_proposal" if n == 0 else None')


def observe_no_article_refused():
    v = _link_view(_link_item())
    return {"refused": [r for r in v["refused"] if r["position"] != "POS-7"], "counts": v["counts"],
            "unlinked": [v["positions"][p] for p in ("POS-8", "POS-9", "POS-10")]}


def expected_no_article_refused():
    return {"refused": [{"position": "POS-8", "article": None, "reason": "no_article"},
                        {"position": "POS-9", "article": "A9", "reason": "article_not_in_excerpt"},
                        {"position": "POS-10", "article": "A3", "reason": "no_proposal"}],
            "counts": {"linked": 3, "proposal_level": 3, "no_article": 1, "article_not_in_excerpt": 1,
                       "no_proposal": 1, "several_proposals": 1},
            "unlinked": [(None, None, None), ("A9", None, None), ("A3", None, None)]}


def neutralise_no_article_refused():
    return with_source(sc, "link_article_positions", 'if aid is None or aid == "":', 'if False:')


def _shadow_builds(n=5):
    """The fixture builds with the persona's own support on A2 proposal 1 (POS-7): its article-level oppose POS-2
    is then shadowed by the plan's `applicable` unless linked."""
    out = _builds(n)
    for b in out:
        b["positions"].append({"id": "POS-7", "party": "ALPHA", "round": 1, "article": "A2", "proposal": 1,
                               "stance": "support", "quote": "We could support assessed contributions.",
                               "source": "fixture 7"})
    return out


def _link_config(folder, on):
    value = json.loads(sc.DEV_CONFIG.read_text(encoding="utf-8"))
    value[sc.ARTICLE_LINK_KEY] = on
    path = Path(folder) / ("dev_%s.json" % on)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def observe_off_leaves_output_unchanged():
    with nb.setdir(builds=_shadow_builds()) as root, tempfile.TemporaryDirectory(prefix="neglink_") as td:
        items, keys = na.read_items(root), sc.read_keys(root)
        answers = _answers(items)
        plain = {"N1": sc.position_oppose_report(items, keys, sc.build_positions(root), answers, resamples=100),
                 "P3": sc.margin_threshold_report(items, keys, answers, None, resamples=100)}
        off = sc.dev_figures(root, answers, config_path=_link_config(td, False), resamples=100)
        on = sc.dev_figures(root, answers, config_path=_link_config(td, True), resamples=100)
        rows = sc.replies_by_item(answers, "system_advice")
        item = items["fx-k2-a"]
        reply = rows["fx-k2-a"]["reply"]
        return {"shipped": sc.article_link_on(sc.dev_config()),
                "off_equal": {k: off[k] == plain[k] for k in ("N1", "P3")}, "off_record": off["article_link"],
                "off_python_equal": sc.system_python(sc.linked_item(item, False), reply) == sc.system_python(item, reply),
                "units": (off["N1"]["real"]["units"], on["N1"]["real"]["units"]), "on_record": on["article_link"],
                "refused_not_bool": caught(lambda: sc.dev_config(_bad_link(td)))}


def _bad_link(folder):
    value = json.loads(sc.DEV_CONFIG.read_text(encoding="utf-8"))
    value[sc.ARTICLE_LINK_KEY] = "yes"
    path = Path(folder) / "dev_bad.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def expected_off_leaves_output_unchanged():
    # Off: the figures and the Python step are what they were. On: POS-2 joins POS-7 on P-A2-1 in each of the five
    # items (30 units to 35); per item POS-2, POS-4, POS-6 linked, POS-1, POS-3, POS-5, POS-7 already on a proposal.
    zero = {k: 0 for k in sc.LINK_REFUSALS}
    return {"shipped": False, "off_equal": {"N1": True, "P3": True}, "off_record": "off", "off_python_equal": True,
            "units": (30, 35), "on_record": {"on": True, "counts": dict(zero, linked=15, proposal_level=20)},
            "refused_not_bool": "raised ValueError"}


def neutralise_off_leaves_output_unchanged():
    return with_source(sc, "linked_item", 'if not on or item.get("game"):', 'if item.get("game"):')


GROUPS = {
    "531": ("choice_steps_first", "refused_generated_drops_its_field", "stance_arms_side_by_side",
            "choice_margins_saved"),
    "532": ("threshold_on_the_largest_margin", "reported_with_and_without", "tuned_off_the_deciding_set"),
    "533": ("oppose_recall_and_precision", "clustered_by_item"),
    "535": ("single_proposal_linked", "several_proposals_not_linked", "no_article_refused",
            "off_leaves_output_unchanged"),
}
WHAT = {"531": "the stepwise chain's choice steps before its generated ones under the declared choice_first order, a "
               "refused generated step dropping only its own field, the stance context's full and trimmed arms side "
               "by side and marked, each choice step's probabilities saved and carried as oppose margins",
        "532": "a proposal's conflict by one declared threshold on the persona's largest oppose margin, reported "
               "with and without, tuned on a split that is not the deciding set",
        "533": "oppose recall and precision over all positions against the build's stances, item-clustered "
               "intervals, beside the bar and never inside it",
        "535": "D-758: the composition step links an article-level position to its article's single proposal from "
               "structure alone, leaves an article with several proposals article-level and refuses a position with "
               "no article, outside the excerpt or on an article with no proposal, each counted; off by default "
               "and off leaves every figure unchanged"}


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
            return "FAIL", "%s as built: %s" % (name, str(first)[:700])
        if broken == expected():
            return "FAIL", "%s still passes when neutralised" % name
        if again != expected():
            return "FAIL", "%s after restore: %s" % (name, str(again)[:400])
        done.append(name)
    return "PASS", "%d proofs, each neutralise, fail, restore, pass, no model: %s (%s)" % (
        len(done), WHAT[number], ", ".join(done))


if __name__ == "__main__":
    for n in (sys.argv[1:] or sorted(GROUPS)):
        status, detail = run_group(n)
        print(n, status, detail)
