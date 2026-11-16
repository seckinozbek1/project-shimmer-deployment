#!/usr/bin/env python3
"""Checks 485 to 488 (lane contradoc-d652): the read-only tools behind D-652, D-656, D-663/D-672 and D-694 item 1,
each proven on invented fixtures in a temporary folder: no model, no provider, no run, no answer key.

485, D-652: tools/contradoc_ok_effect.py classes a saved "does not contradict" answer as today's
    paired_review.judged_item_refusal does (INFRA-055), and a document can turn CLEAR under ContraDoc's `each`
    reading only when every unit holds an ok answer and none an irregular one; its shares carry exact intervals.
486, D-656: tools/neg_judge_calibration.py moves a judge that grades every entry 2 to the floor by per-grade
    offsets judged out of fold (leave one item out), refuses any pilot item, and reads too few entries as
    too_few_entries, never at_floor.
487, D-672: tools/output_side_read.py counts the auditor's drops under system_audit, meets the bar only when the
    after pass drops nothing but not_asked on the schema groups, and counts a choice decision as the model's own
    top token only when it was.
488, D-694 item 1: tools/gpu_release_read.py reads the server's hand-back by scripts/vllm_link.YIELD_EVENT, and its
    bar is not met when an entry did not reach its end.
Each proof neutralised, failed, restored and passed (scripts/effect_proof.py).
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from effect_proof import prove_effect  # noqa: E402
import contradoc_ok_effect as coe  # noqa: E402
import gpu_release_read as grr  # noqa: E402
import neg_judge_calibration as njc  # noqa: E402
import output_side_read as osr  # noqa: E402


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding="utf-8")


class _Proofs(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        type(self).evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


# ---------------------------------------------------------------------------- 485

UNIT_TEXT = "The supplier shall deliver every order within ten days. The supplier may deliver orders after thirty days."
QUOTE_A = "The supplier shall deliver every order within ten days."
QUOTE_B = "The supplier may deliver orders after thirty days."
OK_PLAIN = {"relation": "contradiction", "record_verdict": "ok"}
OK_SECOND_UNIT = {"relation": "contradiction", "record_verdict": "ok", "compared_unit_id": "u02"}
NO_VERDICT = {"relation": "contradiction"}
IRREGULAR = {"relation": "contradiction", "record_verdict": "irregular", "quote": QUOTE_A, "quote_b": QUOTE_B}


def _contradoc_run(root, documents):
    """documents: {doc: {unit: [items]}} -> a run folder with a pairing map and one reply per unit."""
    pairing, n = {}, 0
    for doc, units in documents.items():
        calls = []
        for unit, items in units.items():
            n += 1
            call = "call%04d" % n
            calls.append({"call_id": call, "unit_id": unit, "rule_id": "CONV-001", "plan_kind": "uncomputable"})
            _write(root / "audit" / "model_replies" / ("%06d_%s.json" % (n, call)),
                   {"call_id": call, "reply": {"text": json.dumps({"agent": "A", "doc_id": unit, "items": items})}})
        pairing[doc] = {"document_id": doc, "units": [{"unit_id": u} for u in units], "judging_calls": calls,
                        "uncomputable_refused": [{"unit_id": "u01", "reason": coe.CONTRADICTION_NOT_IRREGULAR}]}
    _write(root / "audit" / "pairing_map.json", pairing)
    return root


class OkEffectChecks(_Proofs):
    evidence = []

    def _run(self):
        return _contradoc_run(self.tmp / "run", {
            "docA": {"u01": [OK_PLAIN], "u02": [OK_PLAIN]},             # every unit ok: can turn CLEAR
            "docB": {"u01": [OK_PLAIN, IRREGULAR]},                     # ok and irregular in one unit: never
            "docC": {"u01": [OK_PLAIN], "u02": [NO_VERDICT]},          # one unit without an ok: never
        })

    def test_a_each_reading_needs_every_unit_ok_and_no_irregular(self):
        run = self._run()
        observe = lambda: [coe.effect([run])["each_can_turn_clear"]["count"], coe.effect([run])["v2_can_move"]["count"],
                           coe.effect([run])["totals"]["ok"], coe.effect([run])["totals"]["other_verdict"]]
        self.assertEqual(observe(), [1, 2, 4, 1])
        loose = lambda units, ok, irregular: bool(units) and set(units) <= set(ok)
        self.prove("each reading: every unit ok, no irregular", observe, [1, 2, 4, 1],
                   lambda: patch.object(coe, "each_can_turn_clear", loose))

    def test_b_classes_agree_with_todays_refusal(self):
        import paired_review as pr

        def observe():
            out = []
            for item in (OK_PLAIN, OK_SECOND_UNIT, NO_VERDICT, IRREGULAR):
                reason = pr.judged_item_refusal(dict(item, unit_id="u01"), {}, [], UNIT_TEXT)
                verdict = coe.verdict_of(item)
                tool = (coe.ok_class(item) if verdict == coe.OK else
                        ("kept" if verdict == coe.IRREGULAR else coe.CONTRADICTION_NOT_IRREGULAR))
                kept_by_tool = tool in (coe.OK_KEPT, "kept")
                out.append(kept_by_tool == (reason is None)
                           and (tool != coe.CONTRADICTION_NOT_IRREGULAR or reason == pr.CONTRADICTION_NOT_IRREGULAR))
            return out
        self.assertEqual(observe(), [True, True, True, True])
        self.prove("ok answers classed as INFRA-055 keeps them", observe, [True, True, True, True],
                   lambda: patch.object(coe, "ok_class", lambda item: coe.OK_REFUSED))

    def test_c_shares_carry_exact_intervals(self):
        observe = lambda: [coe.exact_interval(0, 22), coe.exact_interval(3, 10), coe.exact_interval(0, 4)]
        expected = [[0.0, 0.1544], [0.0667, 0.6525], [0.0, 0.6024]]
        self.assertEqual(observe(), expected)
        self.prove("Clopper-Pearson intervals", observe, expected,
                   lambda: patch.object(coe, "_binom_cdf", lambda k, n, p: 1.0 - p))


# ---------------------------------------------------------------------------- 486

def _judge_rows(items, per_item, *, informative=True):
    """Every entry graded 2 by the raw judge; the checker's grade cycles 0, 1, 2 (7 of 0 and 1 in every 10 when
    `informative` is False, the pilot's shape)."""
    rows, sheet, cycle = [], [], ("0", "1", "2", "0", "1")
    probs = {"0": (0.35, 0.05, 0.6), "1": (0.05, 0.35, 0.6), "2": (0.05, 0.05, 0.9)}
    for i in range(items):
        for j in range(per_item):
            gold = cycle[(i + j) % len(cycle)]
            p = probs[gold] if informative else (0.2, 0.2, 0.6)
            entry = "e%02d_%02d" % (i, j)
            rows.append({"entry_id": entry, "item_id": "item%02d" % i,
                         "decision": {"answers": [{"label": g, "probability": q} for g, q in zip(njc.GRADES, p)]}})
            sheet.append({"entry_id": entry, "grade": gold})
    return {"schema": njc.ROWS_SCHEMA, "rows": rows}, {"entries": sheet}


class JudgeCalibrationChecks(_Proofs):
    evidence = []

    def test_a_offsets_move_an_always_two_judge_to_the_floor_out_of_fold(self):
        rows, sheet = _judge_rows(8, 5)
        observe = lambda: [njc.calibrate(rows, sheet, [], resamples=50)[k] for k in ("verdict",)] + [
            njc.calibrate(rows, sheet, [], resamples=50)["uncalibrated"]["kappa"] == 0.0]
        self.assertEqual(observe(), ["at_floor", True])
        self.prove("offsets fitted out of fold reach the floor", observe, ["at_floor", True],
                   lambda: patch.object(njc, "GRID", (0.0,)))

    def test_b_a_pilot_item_is_refused(self):
        rows, sheet = _judge_rows(8, 5)

        def observe():
            try:
                njc.calibrate(rows, sheet, ["item03"], resamples=10)
            except ValueError as exc:
                return "refused" if "excluded item" in str(exc) else "other"
            return "read"
        self.assertEqual(observe(), "refused")
        self.prove("the pilot's items never calibrate the judge", observe, "refused",
                   lambda: patch.object(njc, "excluded_item", lambda item_id, excluded: False))

    def test_c_too_few_entries_is_never_at_floor(self):
        rows, sheet = _judge_rows(4, 5)        # 20 entries, 4 items: below MIN_ENTRIES and MIN_ITEMS
        observe = lambda: njc.calibrate(rows, sheet, [], resamples=10)["verdict"]
        self.assertEqual(observe(), "too_few_entries")
        self.prove("too few entries", observe, "too_few_entries",
                   lambda: _patched(njc, MIN_ENTRIES=0, MIN_ITEMS=0))


@contextmanager
def _patched(module, **values):
    with patch.multiple(module, **values):
        yield


# ---------------------------------------------------------------------------- 487

def _answers(advice_drops, audit_drops, validate_drops):
    return {"rows": [
        {"group": "system_advice", "form": "advice", "drops": dict({"proposals.stance": advice_drops} if advice_drops else {},
                                                                    **({"audit": audit_drops} if audit_drops else {}))},
        {"group": "validate", "form": "validate", "drops": {"mapping": validate_drops} if validate_drops else {}},
        {"group": "judge", "form": "judge", "drops": {}}]}


def _after_pass(root):
    rows, n = [], 0
    def add(group, record):
        nonlocal n
        n += 1
        call = "c%03d" % n
        rows.append({"prompt_id": "p%03d" % n, "group": group, "call_id": call, "seconds": 2.0, "failure": None})
        _write(root / "audit" / "model_replies" / ("%06d_%s.json" % (n, call)), dict(record, call_id=call, backend_ok=True))
    add("system_advice", {"decoding_constraint": {"steps": 40, "interventions": 2, "first_intervention_step": 5, "dead_end": False}})
    add("validate", {"decoding_constraint": {"steps": 20, "interventions": 0, "first_intervention_step": None, "dead_end": False}})
    add("system_audit", {"decision": {"answers": [{"label": "supported", "probability": 0.8}, {"label": "unsupported", "probability": 0.2}],
                                      "declared_mass": 0.5, "undeclared_top": {"probability": 0.5}, "settled": True}})
    add("judge", {"decision": {"answers": [{"label": "0", "probability": 0.9}, {"label": "1", "probability": 0.05},
                                           {"label": "2", "probability": 0.05}],
                               "declared_mass": 0.9, "undeclared_top": {"probability": 0.1}, "settled": True}})
    _write(root / "replay_measurement.json", {"rows": rows})
    return root


class OutputSideChecks(_Proofs):
    evidence = []

    def test_a_bar_met_only_with_no_form_drop(self):
        run = _after_pass(self.tmp / "after")
        before, after = _answers({"not_declared": 3}, {"json_invalid": 1}, {"no_json_object": 2}), _answers(None, None, {"not_asked": 1})
        observe = lambda: osr.read(before, after, run)["bar"]["met"]
        self.assertTrue(observe())
        self.prove("the bar admits not_asked alone", observe, True, lambda: patch.object(osr, "NOT_ASKED", "renamed"))

    def test_b_audit_drops_are_the_auditors(self):
        before = _answers({"not_declared": 3}, {"json_invalid": 1}, None)
        observe = lambda: {g: b["dropped"] for g, b in sorted(osr.drops_by_group(before).items())}
        expected = {"judge": 0, "system_advice": 3, "system_audit": 1, "validate": 0}
        self.assertEqual(observe(), expected)
        self.prove("audit drops under system_audit", observe, expected, lambda: patch.object(osr, "AUDIT_FIELD", "none"))

    def test_c_model_top_token_counted_only_when_it_was(self):
        run = _after_pass(self.tmp / "after")
        observe = lambda: {g: osr.after_records(run)[g]["top_is_model_top"] for g in ("judge", "system_audit")}
        expected = {"judge": 1, "system_audit": 0}
        self.assertEqual(observe(), expected)
        self.prove("top answer against the whole vocabulary", observe, expected,
                   lambda: patch.object(osr, "top_is_model_top", lambda decision: True))


# ---------------------------------------------------------------------------- 488

def _gpu_entry(root, *, reached_end=True, handback=True):
    events = [{"event": "backend_invocation", "agent": "VERIFIER", "backend_success": True, "usage": {"engine": "vllm"}}]
    if handback:
        events.append({"event": "vllm_server_yield", "requests": 40, "close_seconds": 3.5, "start_number": 1})
    events += [{"event": "model_load_start", "model": "final-producer"}, {"event": "model_load_end", "model": "final-producer"},
               {"event": "backend_invocation", "agent": "EDITOR_CLERK", "backend_success": True, "usage": {}},
               {"event": "resource_sample", "gpus": [{"memory_mib": 15800.0}]}]
    _write(root / "logs" / "model_telemetry.jsonl", "\n".join(json.dumps(e) for e in events) + "\n")
    _write(root / "audit" / "run_completion.json", {"state": "completed", "reached_end": reached_end, "exit_code": 0})
    return root


class GpuReleaseChecks(_Proofs):
    evidence = []

    def test_a_handback_read_by_the_links_own_event(self):
        import vllm_link
        run = _gpu_entry(self.tmp / "e1")
        observe = lambda: [grr.read([run])["bar"]["met"], grr.YIELD_EVENT == vllm_link.YIELD_EVENT,
                           grr.read([run])["peak_gpu_memory_mib"]]
        self.assertEqual(observe(), [True, True, 15800.0])
        self.prove("the hand-back event", observe, [True, True, 15800.0],
                   lambda: patch.object(grr, "YIELD_EVENT", "renamed"))

    def test_b_an_entry_short_of_its_end_fails_the_bar(self):
        runs = [_gpu_entry(self.tmp / "e1"), _gpu_entry(self.tmp / "e2", reached_end=False)]
        observe = lambda: [l["count"] for l in grr.read(runs)["bar"]["lines"]][0]
        self.assertEqual(observe(), 1)
        self.prove("an entry short of its end", observe, 1, lambda: patch.object(grr, "completed", lambda entry: True))


# ----------------------------------------------------------------------------

def _run(cls, what):
    cls.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(cls).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", "%d proofs, each neutralise, fail, restore, pass, fixtures only: %s" % (len(cls.evidence), what)


def check_ok_effect():
    return _run(OkEffectChecks, "a saved ok contradiction answer classed as paired_review keeps it under INFRA-055, a "
                                "document CLEAR under `each` only with every unit ok and none irregular, exact intervals")


def check_judge_calibration():
    return _run(JudgeCalibrationChecks, "an always-2 judge brought to the floor by per-grade offsets judged out of fold, "
                                        "a pilot item refused, too few entries never at the floor")


def check_output_side():
    return _run(OutputSideChecks, "audit drops counted under system_audit, the bar met with not_asked alone, the model's "
                                  "own top token counted only when it was")


def check_gpu_release():
    return _run(GpuReleaseChecks, "the hand-back read by vllm_link's own event, an entry short of its end failing the bar")


def main():
    code = 0
    for name, fn in (("485", check_ok_effect), ("486", check_judge_calibration), ("487", check_output_side),
                     ("488", check_gpu_release)):
        status, detail = fn()
        print(name, status, detail)
        code |= status != "PASS"
    return code


if __name__ == "__main__":
    raise SystemExit(main())
